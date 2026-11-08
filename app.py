import re
import time
from datetime import datetime

import streamlit as st

from story_generator import generate_story, continue_story, assess_story_genre
from nlp_analysis import analyze_sentiment, extract_entities


# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Story Studio | AI Story Generator",
    page_icon="auto_stories",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# LIGHTWEIGHT, BUILT-IN STYLING (NO SEPARATE CSS FILE)
# ============================================================
st.markdown(
    """
    <style>
        /* Hide Streamlit's top toolbar */
        [data-testid="stToolbar"] {
            display: none;
        }

        /* Hide the Deploy button */
        [data-testid="stAppDeployButton"] {
            display: none;
        }

        /* Hide Streamlit's header area */
        header[data-testid="stHeader"] {
            background: transparent;
        }
        :root {
            --studio-accent: #6d9eff;
            --studio-accent-hover: #4f83ec;
            --studio-border: rgba(148, 163, 184, 0.22);
        }
        .stApp {
            background:
                radial-gradient(ellipse at 8% 0%, rgba(45, 83, 145, 0.15), transparent 34%),
                #0b1020;
        }
        .block-container {
            max-width: 1500px;
            padding-top: 1.7rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: -0.025em;
        }
        h1 { font-size: clamp(1.8rem, 3vw, 2.35rem) !important; }
        h2 { font-size: 1.25rem !important; }
        .app-subtitle {
            color: #9baaca;
            margin-top: -0.45rem;
            margin-bottom: 1.2rem;
            font-size: 0.93rem;
        }
        .section-kicker {
            color: #9baaca;
            font-size: 0.86rem;
            margin-top: -0.5rem;
            line-height: 1.5;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(16, 24, 43, 0.76);
            border: 1px solid var(--studio-border);
            border-radius: 16px;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.10);
        }
        div[data-testid="stTextArea"] textarea {
            background: #111a2e !important;
            border: 1px solid #2a3855 !important;
            border-radius: 11px !important;
            line-height: 1.65 !important;
            font-size: 0.95rem !important;
        }
        div[data-testid="stTextArea"] textarea:focus {
            border-color: var(--studio-accent) !important;
            box-shadow: 0 0 0 1px var(--studio-accent) !important;
        }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background: #111a2e;
            border-color: #2a3855;
            border-radius: 10px;
        }
        div.stButton > button, div.stDownloadButton > button {
            border-radius: 10px;
            min-height: 2.65rem;
            font-weight: 600;
            transition: border-color 120ms ease, background 120ms ease, transform 120ms ease;
        }
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #4e83f1, #3568d4) !important;
            border: 1px solid #5b8df5 !important;
            color: #ffffff !important;
            box-shadow: 0 5px 16px rgba(53, 104, 212, 0.22);
        }
        div.stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #6395ff, #4278e5) !important;
            border-color: #80a7ff !important;
            transform: translateY(-1px);
        }
        div.stButton > button[kind="secondary"], div.stDownloadButton > button {
            background: #151e31 !important;
            border: 1px solid #2c3a55 !important;
        }
        div.stButton > button[kind="secondary"]:hover, div.stDownloadButton > button:hover {
            background: #1b2942 !important;
            border-color: #668bd0 !important;
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid rgba(148, 163, 184, 0.13);
            border-radius: 11px;
            padding: 0.65rem 0.75rem;
        }
        div[data-testid="stMetricLabel"] {
            color: #a8b5ce !important;
        }
        div[data-testid="stProgress"] > div {
            background: #26334b;
            border-radius: 99px;
        }
        div[data-testid="stProgress"] div[role="progressbar"] {
            background: linear-gradient(90deg, #5289f4, #76a7ff);
            border-radius: 99px;
        }
        .story-placeholder {
            color: #a8b5ce;
            padding: 1rem 0;
            line-height: 1.8;
        }
        .story-reading-note {
            color: #8c9bb8;
            font-size: 0.83rem;
        }
        hr {
            border-color: rgba(148, 163, 184, 0.17);
        }
        @media (max-width: 900px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================
if "story" not in st.session_state:
    st.session_state["story"] = ""

if "story_idea" not in st.session_state:
    st.session_state["story_idea"] = ""

if "story_genre" not in st.session_state:
    st.session_state["story_genre"] = "Fantasy"

if "story_history" not in st.session_state:
    st.session_state["story_history"] = []

if "history_selection" not in st.session_state:
    st.session_state["history_selection"] = None

if "generation_seconds" not in st.session_state:
    st.session_state["generation_seconds"] = None

if "continuation_seconds" not in st.session_state:
    st.session_state["continuation_seconds"] = None

if "genre_assessment" not in st.session_state:
    st.session_state["genre_assessment"] = None

if "genre_assessment_genre" not in st.session_state:
    st.session_state["genre_assessment_genre"] = None


def add_to_history(story_text, idea, genre, action):
    """Save a snapshot to this browser session's Streamlit state."""
    if not story_text or not story_text.strip():
        return

    history = st.session_state["story_history"]
    # Avoid adding an identical consecutive snapshot.
    if history and history[-1].get("story") == story_text.strip():
        return

    history.append(
        {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "title": get_story_title(story_text),
            "story": story_text.strip(),
            "idea": idea,
            "genre": genre,
            "action": action,
            "created_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        }
    )
    # Keep the session history bounded.
    if len(history) > 50:
        del history[:-50]


def validate_story_idea(idea):
    idea = idea.strip()

    if not idea:
        return False, "Please enter a story idea."

    # Extract words and remove punctuation for checking.
    words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?", idea)

    if len(idea) < 10 or len(words) < 3:
        return (
            False,
            "Please enter a clearer story idea using at least 3 words."
        )

    # Check the overall balance of vowels and consonants.
    letters = re.sub(r"[^a-z]", "", idea.lower())
    vowels = sum(1 for char in letters if char in "aeiou")

    if len(letters) >= 15 and vowels / len(letters) < 0.18:
        return (
            False,
            "Your idea looks like random text. "
            "Please enter a readable story idea."
        )

    # Look for unusually long consonant sequences in individual words.
    suspicious_words = 0

    for word in words:
        cleaned_word = re.sub(r"[^a-z]", "", word.lower())

        if len(cleaned_word) >= 5:
            word_vowels = sum(
                1 for char in cleaned_word if char in "aeiou"
            )

            if word_vowels == 0 or re.search(
                r"[^aeiou]{5,}", cleaned_word
            ):
                suspicious_words += 1

    if suspicious_words >= 2:
        return (
            False,
            "Some words look unusual or incomplete. "
            "Please check your story idea and try again."
        )

    return True, ""


def get_story_title(story_text):
    """Use the first short title-like line, when available."""
    nonempty_lines = [line.strip() for line in story_text.splitlines() if line.strip()]
    if not nonempty_lines:
        return "Generated Story"

    first_line = re.sub(r"^\s{0,3}#{1,6}\s*", "", nonempty_lines[0])
    first_line = first_line.replace("**", "").replace("__", "").strip()

    looks_like_title = (
        len(first_line) <= 100
        and len(first_line.split()) <= 15
        and not re.search(r"[.!?]$", first_line)
    )
    return first_line if looks_like_title else "Generated Story"


def get_story_body(story_text):
    """Remove a title-like first line from the displayed body."""
    nonempty_lines = [line.strip() for line in story_text.splitlines() if line.strip()]
    if not nonempty_lines:
        return ""

    title = get_story_title(story_text)
    first_line = re.sub(r"^\s{0,3}#{1,6}\s*", "", nonempty_lines[0])
    first_line = first_line.replace("**", "").replace("__", "").strip()

    if title != "Generated Story" and first_line == title and len(nonempty_lines) > 1:
        return "\n\n".join(nonempty_lines[1:])
    return story_text.strip()


def analyze_current_story(story_text):
    """Run NLP analysis safely and return consistent values."""
    fallback_scores = {"pos": 0.0, "neu": 0.0, "neg": 0.0, "compound": 0.0}
    try:
        sentiment, scores = analyze_sentiment(story_text)
        entities = extract_entities(story_text)
        return sentiment, scores, entities, None
    except Exception as exc:
        return "Unavailable", fallback_scores, [], str(exc)


# ============================================================
# HEADER
# ============================================================
header_icon, header_text = st.columns([0.002, 2.0], vertical_alignment="center")

with header_text:
    st.title("Story Studio")
    st.markdown(
        '<p class="app-subtitle">A calm workspace for original stories, powered by local AI and NLP.</p>',
        unsafe_allow_html=True,
    )

st.divider()


# ============================================================
# MAIN TWO-COLUMN WORKSPACE
# ============================================================
left_col, right_col = st.columns([0.88, 1.12], gap="large")

with left_col:
    st.subheader(":material/auto_awesome: Create your story")
    st.markdown(
        '<p class="section-kicker">Start with your own idea, then choose a genre and length.</p>',
        unsafe_allow_html=True,
    )

    story_idea_input = st.text_area(
        "Story idea",
        value=st.session_state.get("story_idea", ""),
        placeholder="Describe your characters, setting, conflict, or a story idea...",
        height=145,
        help="Write your own idea. There are no predefined prompts.",
        key="story_idea_input",
    )

    genre = st.selectbox(
        "Genre",
        [
            "Fantasy",
            "Horror",
            "Mystery",
            "Science Fiction",
            "Adventure",
            "Romance",
            "Thriller",
        ],
        index=[
            "Fantasy",
            "Horror",
            "Mystery",
            "Science Fiction",
            "Adventure",
            "Romance",
            "Thriller",
        ].index(st.session_state.get("story_genre", "Fantasy")),
        key="genre_input",
    )

    story_length = st.selectbox(
        "Story length",
        ["Short (~200 words)", "Medium (~500 words)", "Large (~700 words)"],
        index=0,
        key="story_length_input",
    )

    st.markdown("")

    # Generate a new story or regenerate using the current idea and settings.
    generate_label = ":material/refresh: Regenerate Story" if st.session_state["story"] else ":material/auto_awesome: Generate Story"
    if st.button(generate_label, type="primary", use_container_width=True, key="generate_story_button"):
        is_valid, error_message = validate_story_idea(story_idea_input)

        if not is_valid:
            st.warning(error_message)
        else:
            with st.spinner("Creating your story... This may take a little while on your laptop."):
                try:
                    generation_started = time.perf_counter()
                    generated_story = generate_story(
                        story_idea_input.strip(),
                        genre,
                        story_length,
                    )
                    generation_seconds = time.perf_counter() - generation_started
                    if not generated_story or not generated_story.strip():
                        st.error("The model returned an empty response. Please try again.")
                    else:
                        st.session_state["story"] = generated_story.strip()
                        st.session_state["story_idea"] = story_idea_input.strip()
                        st.session_state["story_genre"] = genre
                        st.session_state["generation_seconds"] = generation_seconds
                        # Genre assessment is a second local-model inference and can take extra time.
                        st.session_state["genre_assessment"] = None
                        st.session_state["genre_assessment_genre"] = genre
                        add_to_history(
                            generated_story.strip(),
                            story_idea_input.strip(),
                            genre,
                            "Generated",
                        )
                        st.rerun()
                except Exception as exc:
                    st.error("Something went wrong while generating the story.")
                    st.exception(exc)

    # Continue Story remains in the left control panel as requested.
    current_story_words = len(st.session_state["story"].split())
    story_limit_reached = current_story_words >= 1200

    if story_limit_reached:
        st.caption("The story has reached the 1,200-word limit. It cannot be continued further.")
    else:
        st.caption(f"Story limit: {current_story_words:,} / 1,200 words")

    if st.button(
        ":material/arrow_forward: Continue Story",
        use_container_width=True,
        disabled=not bool(st.session_state["story"]) or story_limit_reached,
        key="continue_story_button",
    ):
        current_story = st.session_state["story"]
        current_genre = st.session_state.get("story_genre", genre)
        current_idea = st.session_state.get("story_idea", story_idea_input.strip())

        with st.spinner("Continuing your story..."):
            try:
                continuation_started = time.perf_counter()
                continuation = continue_story(current_story, current_genre)
                continuation_seconds = time.perf_counter() - continuation_started
                if not continuation or not continuation.strip():
                    st.error("The model returned an empty continuation. Please try again.")
                else:
                    updated_story = current_story.rstrip() + "\n\n" + continuation.strip()
                    st.session_state["story"] = updated_story
                    st.session_state["continuation_seconds"] = continuation_seconds
                    add_to_history(updated_story, current_idea, current_genre, "Continued")
                    st.rerun()
            except Exception as exc:
                st.error("Something went wrong while continuing the story.")
                st.exception(exc)

    # Download is stacked with the other controls, but is disabled before generation.
    current_story_for_download = st.session_state["story"]
    st.download_button(
        ":material/download: Download Story (.txt)",
        data=current_story_for_download,
        file_name="ai_generated_story.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not bool(current_story_for_download),
        key="download_story_button",
    )

    if st.button(
        ":material/delete: Clear Current Story",
        use_container_width=True,
        disabled=not bool(st.session_state["story"]),
        key="clear_current_story_button",
    ):
        st.session_state["story"] = ""
        st.rerun()


with right_col:
    story = st.session_state["story"]
    st.subheader(":material/menu_book: Generated story")
    if story:
        story_title = get_story_title(story)
        story_body = get_story_body(story)
        displayed_word_count = len(story.split())
        st.caption(
            f"{st.session_state.get('story_genre', genre)}"
            f"  ·  {displayed_word_count:,} / 1,200 words"
        )

        # A fixed-height container keeps the story panel scrollable.
        with st.container(height=550, border=True):
            st.markdown(f"### {story_title}")
            st.markdown(story_body)
    else:
        with st.container(height=600, border=True):
            st.markdown("### Your story will appear here")
            st.markdown(
                """
                <div class="story-placeholder">
                    Enter an idea on the left and select <b>Generate Story</b>.
                    Your generated story will appear in this reading panel.
                </div>
                """,
                unsafe_allow_html=True,
            )



# ============================================================
# NLP ANALYSIS AND STATISTICS
# ============================================================
story = st.session_state["story"]
if story:
    sentiment, scores, entities, analysis_error = analyze_current_story(story)
    word_count = len(story.split())
    character_count = len(story)
    sentence_count = len(re.findall(r"[.!?]+(?=\s|$)", story))

    # Deduplicate entities for display, while retaining the full count for statistics.
    unique_entities = []
    seen_entities = set()
    for entity in entities:
        entity_text = str(entity.get("text", "")).strip()
        label = str(entity.get("label", ""))
        key = (entity_text.casefold(), label)
        if entity_text and key not in seen_entities:
            seen_entities.add(key)
            unique_entities.append({"text": entity_text, "label": label})

    if analysis_error:
        st.warning("The story was generated, but NLP analysis could not be completed.")
        with st.expander("Show analysis error"):
            st.code(analysis_error)
else:
    sentiment = "—"
    scores = {"pos": 0.0, "neu": 0.0, "neg": 0.0, "compound": 0.0}
    entities = []
    unique_entities = []
    word_count = 0
    character_count = 0
    sentence_count = 0


# ============================================================
# FOUR BOTTOM CARDS
# ============================================================
st.divider()
st.subheader("Story insights")
st.markdown(
    '<p class="section-kicker">A quick overview of your current story and saved session history.</p>',
    unsafe_allow_html=True,
)

card1, card2, card3, card4 = st.columns(4, gap="medium")

with card1:
    with st.container(border=True, height=350):
        st.markdown("### :material/insert_chart: Statistics")
        st.metric("Words", f"{word_count:,}")
        stat_left, stat_right = st.columns(2)
        stat_left.metric("Characters", f"{character_count:,}")
        stat_right.metric("Sentences", f"{sentence_count:,}")
        if story:
            st.caption("Counts update when the current story changes.")
        else:
            st.caption("Generate a story to view its statistics.")

with card2:
    with st.container(border=True, height=350):
        st.markdown("### :material/monitor_heart: Sentiment analysis")
        if story:
            sentiment_icon = {
                "Positive": "✓",
                "Negative": "−",
                "Neutral": "○",
            }.get(sentiment, "◉")
            st.markdown(f"**{sentiment_icon} {sentiment}**")
            positive = float(scores.get("pos", 0.0))
            neutral = float(scores.get("neu", 0.0))
            negative = float(scores.get("neg", 0.0))
            st.caption(
                f"Positive {positive * 100:.1f}%  ·  "
                f"Neutral {neutral * 100:.1f}%  ·  "
                f"Negative {negative * 100:.1f}%"
            )
            st.progress(max(0.0, min(1.0, positive)))
            st.caption(f"Compound score: {float(scores.get('compound', 0.0)):.3f}")
            with st.expander("View sentiment breakdown"):
                st.write(f"Positive: {positive * 100:.1f}%")
                st.write(f"Neutral: {neutral * 100:.1f}%")
                st.write(f"Negative: {negative * 100:.1f}%")
                st.caption("VADER estimates sentiment from wording; it is not a definitive interpretation.")
        else:
            st.caption("Sentiment results will appear after generation.")

with card3:
    with st.container(border=True, height=350):
        st.markdown("### :material/document_scanner: Named entities")
        st.metric("Detected entities", f"{len(unique_entities):,}")
        if unique_entities:
            entity_groups = {
                "People": [],
                "Places": [],
                "Organizations": [],
                "Dates and times": [],
                "Other": [],
            }
            for entity in unique_entities:
                label = entity["label"]
                if label == "PERSON":
                    group = "People"
                elif label in {"GPE", "LOC", "FAC"}:
                    group = "Places"
                elif label == "ORG":
                    group = "Organizations"
                elif label in {"DATE", "TIME"}:
                    group = "Dates and times"
                else:
                    group = "Other"
                entity_groups[group].append(entity["text"])

            preview_items = unique_entities[:4]
            st.caption(
                ", ".join(item["text"] for item in preview_items)
                + (" …" if len(unique_entities) > len(preview_items) else "")
            )
            with st.expander("View all detected entities"):
                for group, items in entity_groups.items():
                    if items:
                        st.markdown(f"**{group}**")
                        st.caption(", ".join(items))
        elif story:
            st.caption("No named entities detected in this story.")
        else:
            st.caption("Entities will appear after generation.")

with card4:
    with st.container(border=True, height=350):
        st.markdown("### :material/history: Story history")
        history = st.session_state["story_history"]
        st.metric("Saved versions", len(history))
        if history:
            history_options = {
                f"{item['created_at']} · {item['title'][:35]} ({item['action']})": item["id"]
                for item in reversed(history)
            }
            selected_label = st.selectbox(
                "Choose a saved story",
                options=list(history_options.keys()),
                key="saved_story_picker",
                label_visibility="collapsed",
            )
            if st.button(":material/restore: Open selected story", use_container_width=True, key="open_history_button"):
                selected_id = history_options[selected_label]
                selected_item = next(item for item in history if item["id"] == selected_id)
                st.session_state["story"] = selected_item["story"]
                st.session_state["story_idea"] = selected_item["idea"]
                st.session_state["story_genre"] = selected_item["genre"]
                st.session_state["generation_seconds"] = None
                st.session_state["genre_assessment"] = None
                st.session_state["genre_assessment_genre"] = selected_item["genre"]
                st.rerun()
        else:
            st.caption("Your generated stories will be saved here during this session.")


# ============================================================
# GENERATION PERFORMANCE AND GENRE CONSISTENCY — BELOW THE FOUR INSIGHT CARDS
# ============================================================
if st.session_state["story"]:
    perf_col, genre_col = st.columns(2, gap="medium")
    with perf_col:
        with st.container(border=True):
            st.markdown("### :material/timer: Generation performance")
            elapsed = st.session_state.get("generation_seconds")
            continuation_elapsed = st.session_state.get("continuation_seconds")

            if elapsed is not None:
                st.metric("Initial story generation", f"{elapsed:.2f} sec")
            else:
                st.caption("Initial generation time is unavailable for this restored story.")

            if continuation_elapsed is not None:
                st.metric("Last continuation", f"{continuation_elapsed:.2f} sec")
            else:
                st.caption("Continue the story to measure its generation time.")

            st.caption(
                "The first generation may include model loading if the model was not cached. "
                "Genre-check time is measured separately."
            )

    with genre_col:
        with st.container(border=True):
            st.markdown("### :material/verified: Genre consistency")
            selected_genre = st.session_state.get("story_genre", genre)
            assessment = st.session_state.get("genre_assessment")
            assessment_genre = st.session_state.get("genre_assessment_genre")
            if assessment and assessment_genre == selected_genre:
                status = assessment["status"]
                status_labels = {
                    "MATCH": "Likely match",
                    "PARTIAL MATCH": "Partial match / mixed genre",
                    "MISMATCH": "Possible mismatch",
                    "UNCERTAIN": "Uncertain",
                }
                st.markdown(f"**Selected genre:** {selected_genre}")
                st.markdown(f"**Assessment:** {status_labels.get(status, status.title())}")
                st.caption(f"Best fit: {assessment['best_fit']}")
                st.write(assessment["reason"])
                st.caption("AI assessment is an estimate and may be incorrect.")
            else:
                st.markdown(f"**Selected genre:** {selected_genre}")
                if st.button("Check genre consistency", key="assess_genre_button", use_container_width=True):
                    with st.spinner("Checking whether the story matches its selected genre..."):
                        try:
                            result = assess_story_genre(
                                st.session_state["story"], selected_genre
                            )
                            st.session_state["genre_assessment"] = result
                            st.session_state["genre_assessment_genre"] = selected_genre
                            st.rerun()
                        except Exception as exc:
                            st.error("Genre assessment failed. Your generated story is still available.")
                            st.caption(str(exc))
                st.caption("This uses the local Qwen model again, so the check may take additional time.")


# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption("Story Studio · Local AI generation · Natural Language Processing")
