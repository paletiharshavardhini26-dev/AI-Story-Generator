"""Local story generation and genre consistency assessment using Qwen."""

import os
import re
from functools import lru_cache

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"


@lru_cache(maxsize=1)
def _load_model():
    """Load the model once and reuse it for subsequent generations."""
    model_name = os.getenv("STORY_MODEL", DEFAULT_MODEL)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if torch.cuda.is_available():
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float16, device_map="auto"
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_name, torch_dtype=torch.float32
            )
            model.to("cpu")
        model.eval()
        return tokenizer, model
    except Exception as exc:
        raise RuntimeError(
            f"Could not load local model '{model_name}'. On the first run, "
            "check your internet connection, disk space, RAM, and package "
            f"installation. Original error: {exc}"
        ) from exc


def _generate(messages, max_new_tokens=900):
    tokenizer, model = _load_model()
    try:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=4096
        )
        device = next(model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                repetition_penalty=1.08,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        prompt_length = inputs["input_ids"].shape[1]
        result = tokenizer.decode(
            output[0][prompt_length:], skip_special_tokens=True
        ).strip()
        if not result:
            raise RuntimeError("The local model returned an empty response.")
        return result
    except torch.cuda.OutOfMemoryError as exc:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise RuntimeError(
            "GPU memory ran out. Try the smaller model "
            "'Qwen/Qwen2.5-0.5B-Instruct' or run on CPU."
        ) from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Local text generation failed: {exc}") from exc


def _word_target(story_length):
    value = str(story_length).lower()
    if "short" in value:
        return "approximately 200 words", 300
    if "medium" in value:
        return "approximately 500 words", 550
    return "approximately 700 words", 750


def _clean_story(text):
    text = text.strip()
    text = re.sub(r"^\s*```(?:text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = re.sub(r"^(?:assistant|story)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def generate_story(story_idea, genre, story_length):
    """Generate a story using the user's idea and selected length."""
    if not isinstance(story_idea, str) or not story_idea.strip():
        raise ValueError("Please enter a story idea before generating.")
    target_length, max_tokens = _word_target(story_length)
    prompt = f"""Write an original, engaging {genre.lower()} story based on this idea.

User's story idea:
{story_idea.strip()}

Requirements:
- Aim for {target_length}.
- Start with a short, compelling title on its own line.
- Include a clear beginning, middle, and ending.
- Develop believable characters and a meaningful conflict.
- Keep events coherent and the writing natural.
- Do not include analysis, notes, or an explanation of the task.
- Return only the title and story."""
    return _clean_story(_generate([{"role": "user", "content": prompt}], max_new_tokens=max_tokens))


def continue_story(existing_story, genre, max_total_words=1200):
    """Continue and conclude the story without exceeding the total word limit."""
    if not isinstance(existing_story, str) or not existing_story.strip():
        raise ValueError("There is no story to continue.")

    existing_story = existing_story.strip()
    existing_word_count = len(existing_story.split())
    remaining_words = max_total_words - existing_word_count

    if remaining_words <= 0:
        raise ValueError(
            f"The story has reached the {max_total_words:,}-word limit. "
            "It cannot be continued further."
        )

    prompt = f"""Finish this {genre.lower()} story from exactly where it ends.

The existing story already contains {existing_word_count} words.
You may write at most {remaining_words} additional words. The final combined
story MUST stay at or below {max_total_words} words, including the existing text.

Requirements:
- Continue directly from the last sentence; do not repeat or summarize existing text.
- The most important goal is to bring the story to a satisfying, clear conclusion now.
- Resolve the main conflict and tie up the most important loose ends.
- Do not introduce a new major conflict or end on a cliffhanger.
- Preserve established characters, setting, tone, and facts.
- Keep the continuation concise enough to fit the remaining word budget.
- Return only the new continuation, with no title, word count, or explanation.
- End with a complete sentence.

Existing story:
{existing_story}"""

    # Approximate word-to-token budget, bounded to avoid runaway generation.
    max_new_tokens = max(40, min(650, int(remaining_words * 2.2)))
    continuation = _clean_story(
        _generate([{"role": "user", "content": prompt}], max_new_tokens=max_new_tokens)
    )

    # Enforce the hard total-word limit even if the model ignores the instruction.
    words = continuation.split()
    if len(words) > remaining_words:
        clipped = " ".join(words[:remaining_words])
        # Prefer a complete sentence if one exists within the permitted budget.
        sentence_ends = list(re.finditer(r"[.!?](?:[\"'’)]*)?(?=\\s|$)", clipped))
        if sentence_ends:
            clipped = clipped[:sentence_ends[-1].end()].strip()
        continuation = clipped

    if not continuation.strip():
        raise RuntimeError(
            "The model did not produce a usable ending within the remaining word limit."
        )

    return continuation


def assess_story_genre(story_text, selected_genre):
    """Ask the same local model to assess genre fit; this is an estimate, not proof."""
    if not isinstance(story_text, str) or not story_text.strip():
        raise ValueError("There is no story to assess.")
    genres = "Fantasy, Horror, Mystery, Science Fiction, Adventure, Romance, Thriller"
    prompt = f"""Assess whether this story fits the user's selected genre.
Selected genre: {selected_genre}
Allowed genre labels: {genres}

Return exactly three lines in this format:
STATUS: MATCH, PARTIAL MATCH, MISMATCH, or UNCERTAIN
BEST_FIT: one allowed genre label (or MIXED)
REASON: one short sentence based on the story content

Be conservative. A story may combine genres. Do not claim certainty if evidence is weak.
Story:
{story_text.strip()[:6000]}"""
    raw = _generate([{"role": "user", "content": prompt}], max_new_tokens=100)
    status_match = re.search(r"STATUS\s*:\s*(MATCH|PARTIAL MATCH|MISMATCH|UNCERTAIN)", raw, re.I)
    best_match = re.search(r"BEST_FIT\s*:\s*([^\n]+)", raw, re.I)
    reason_match = re.search(r"REASON\s*:\s*([^\n]+)", raw, re.I)
    status = status_match.group(1).upper() if status_match else "UNCERTAIN"
    best_fit = best_match.group(1).strip() if best_match else "Could not determine"
    reason = reason_match.group(1).strip() if reason_match else "The model did not return a clear explanation."
    return {"status": status, "best_fit": best_fit, "reason": reason}
