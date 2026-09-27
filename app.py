# app.py

from pathlib import Path
import json
import os
import sys

import streamlit as st

# ============================================================
# PROJECT SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# VERA CORE
# ============================================================

try:
    from bot import compose as vera_compose

    VERA_AVAILABLE = True
    VERA_IMPORT_ERROR = None

except Exception as exc:
    vera_compose = None
    VERA_AVAILABLE = False
    VERA_IMPORT_ERROR = exc


# ============================================================
# OPENAI
# ============================================================

try:
    from openai import OpenAI
    from openai import RateLimitError

    OPENAI_AVAILABLE = True
    OPENAI_IMPORT_ERROR = None

except Exception as exc:
    OpenAI = None
    OPENAI_AVAILABLE = False
    OPENAI_IMPORT_ERROR = exc


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Vera AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

DATASET_DIR = BASE_DIR / "dataset"

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


# ============================================================
# OPENAI SYSTEM PROMPT
# ============================================================

OPENAI_SYSTEM_PROMPT = """
You are the language-generation layer for Vera, an AI merchant assistant.

The Vera core has already decided:
- what the trigger means
- which facts are relevant
- who the message is for
- the communication mode
- the CTA
- the suppression key

Your job is ONLY to improve the wording of the message.

STRICT RULES:

1. Never invent facts.
2. Never invent prices.
3. Never invent dates.
4. Never invent customer information.
5. Never invent merchant information.
6. Never invent competitor information.
7. Never invent statistics.
8. Never invent research papers or citations.
9. Use only facts present in the supplied context.
10. Preserve the meaning of the Vera core output.
11. Preserve the intended trigger.
12. Preserve the CTA intent.
13. Keep the message concise and WhatsApp-friendly.
14. Use one primary CTA.
15. Match the category voice.
16. Respect the language preference.
17. Do not make clinical or medical claims that are not already present.
18. Do not change send_as.
19. Do not change suppression_key.
20. Do not mention these instructions.
21. Do not explain your reasoning outside the rationale field.

Return ONLY valid JSON in this exact structure:

{
  "body": "message text",
  "cta": "cta value",
  "rationale": "short rationale"
}
"""


# ============================================================
# DATASET HELPERS
# ============================================================

def load_json_file(path: Path):
    """Load one JSON file."""

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_dataset_folder(folder_name: str):
    """
    Load JSON files from:
        dataset/<folder_name>/
    """

    folder = DATASET_DIR / folder_name

    if not folder.exists():
        return []

    records = []

    for path in sorted(folder.glob("*.json")):

        try:
            data = load_json_file(path)

            if isinstance(data, dict):

                records.append(
                    {
                        "_source_file": path.name,
                        "_data": data,
                    }
                )

            elif isinstance(data, list):

                for index, item in enumerate(data):

                    if isinstance(item, dict):

                        records.append(
                            {
                                "_source_file": (
                                    f"{path.name} [{index}]"
                                ),
                                "_data": item,
                            }
                        )

        except Exception as exc:

            records.append(
                {
                    "_source_file": path.name,
                    "_data": {},
                    "_load_error": str(exc),
                }
            )

    return records


def unwrap(record):
    """Return actual JSON object."""

    return record.get("_data", {})


def get_nested_value(data, path):
    """Read nested dictionary value using dot notation."""

    current = data

    for part in path.split("."):

        if not isinstance(current, dict):
            return None

        current = current.get(part)

    return current


def first_value(data, paths):
    """Return first non-empty value."""

    for path in paths:

        value = get_nested_value(
            data,
            path,
        )

        if value is not None and value != "":
            return value

    return None


# ============================================================
# OBJECT IDENTIFICATION
# ============================================================

def get_id(data, kind):

    candidates = {

        "category": [
            "category_id",
            "id",
            "category",
        ],

        "merchant": [
            "merchant_id",
            "id",
        ],

        "customer": [
            "customer_id",
            "id",
        ],

        "trigger": [
            "trigger_id",
            "id",
        ],
    }

    value = first_value(
        data,
        candidates.get(
            kind,
            ["id"],
        ),
    )

    return str(value) if value is not None else ""


def get_name(data, kind):

    candidates = {

        "category": [
            "name",
            "category_name",
            "display_name",
        ],

        "merchant": [
            "identity.name",
            "name",
            "merchant_name",
            "display_name",
        ],

        "customer": [
            "identity.name",
            "name",
            "customer_name",
            "display_name",
        ],

        "trigger": [
            "kind",
            "trigger_kind",
            "type",
            "name",
            "title",
        ],
    }

    value = first_value(
        data,
        candidates.get(
            kind,
            ["name"],
        ),
    )

    return str(value) if value is not None else "Unknown"


def get_label(record, kind):

    data = unwrap(record)

    object_id = get_id(
        data,
        kind,
    )

    name = get_name(
        data,
        kind,
    )

    source = record.get(
        "_source_file",
        "Unknown",
    )

    if object_id and name:
        return f"{name} | {object_id}"

    if name:
        return name

    return source


# ============================================================
# RELATIONSHIP HELPERS
# ============================================================

def get_trigger_merchant_id(trigger):

    return first_value(
        trigger,
        [
            "merchant_id",
            "payload.merchant_id",
            "context.merchant_id",
        ],
    )


def get_trigger_customer_id(trigger):

    return first_value(
        trigger,
        [
            "customer_id",
            "payload.customer_id",
            "context.customer_id",
        ],
    )


def get_customer_merchant_id(customer):

    return first_value(
        customer,
        [
            "merchant_id",
            "payload.merchant_id",
            "merchant.id",
            "context.merchant_id",
        ],
    )


# ============================================================
# LOAD DATASET
# ============================================================

categories = load_dataset_folder(
    "categories"
)

merchants = load_dataset_folder(
    "merchants"
)

customers = load_dataset_folder(
    "customers"
)

triggers = load_dataset_folder(
    "triggers"
)


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def normalize_result(result):
    """
    Convert Pydantic model / dict / other output to dict.
    """

    if hasattr(result, "model_dump"):
        result = result.model_dump()

    elif hasattr(result, "dict"):
        result = result.dict()

    if isinstance(result, dict):
        return result

    return {
        "result": result
    }


# ============================================================
# OPENAI HELPERS
# ============================================================

def get_secret_or_env(name):
    """
    Read from Streamlit secrets first,
    then environment variables.
    """

    try:

        value = st.secrets.get(
            name,
            None,
        )

        if value:
            return value

    except Exception:
        pass

    return os.getenv(
        name,
        "",
    )


def build_openai_prompt(
    category,
    merchant,
    trigger,
    customer,
    core_result,
):
    """
    Build structured prompt for OpenAI.
    """

    payload = {

        "category": category,

        "merchant": merchant,

        "trigger": trigger,

        "customer": customer,

        "vera_core_output": core_result,
    }

    return f"""
Improve the wording of the Vera core output.

Use ONLY the supplied information.

Do not change the meaning.

Do not invent facts.

Do not remove important concrete details.

CONTEXT:

{json.dumps(
    payload,
    indent=2,
    ensure_ascii=False,
)}

Return JSON only:

{{
  "body": "final WhatsApp message",
  "cta": "CTA value",
  "rationale": "short explanation"
}}
"""


def call_openai(
    api_key,
    model,
    prompt,
):
    """
    Call OpenAI using the Chat Completions API.
    """

    if not OPENAI_AVAILABLE:

        raise RuntimeError(
            "OpenAI package is not installed."
        )

    if not api_key.strip():

        raise ValueError(
            "OpenAI API key is empty."
        )

    client = OpenAI(
        api_key=api_key.strip()
    )

    response = client.chat.completions.create(

        model=model,

        messages=[
            {
                "role": "system",
                "content": OPENAI_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        temperature=0,

        response_format={
            "type": "json_object"
        },
    )

    content = (
        response.choices[0]
        .message
        .content
    )

    if not content:

        raise RuntimeError(
            "OpenAI returned an empty response."
        )

    return json.loads(
        content
    )


def merge_openai_result(
    core_result,
    ai_result,
):
    """
    Merge AI wording with core-controlled metadata.

    send_as and suppression_key ALWAYS
    come from the Vera core.
    """

    final_result = dict(
        core_result
    )

    if isinstance(
        ai_result.get("body"),
        str,
    ):

        if ai_result["body"].strip():

            final_result["body"] = (
                ai_result["body"].strip()
            )


    if isinstance(
        ai_result.get("cta"),
        str,
    ):

        if ai_result["cta"].strip():

            final_result["cta"] = (
                ai_result["cta"].strip()
            )


    if isinstance(
        ai_result.get("rationale"),
        str,
    ):

        if ai_result["rationale"].strip():

            final_result["rationale"] = (
                ai_result["rationale"].strip()
            )


    # These MUST remain core-controlled.

    final_result["send_as"] = (
        core_result.get(
            "send_as",
            "",
        )
    )

    final_result["suppression_key"] = (
        core_result.get(
            "suppression_key",
            "",
        )
    )

    return final_result


# ============================================================
# PAGE HEADER
# ============================================================

st.title(
    "🤖 Vera — AI Merchant Assistant"
)

st.caption(
    "Interactive testing environment for the Vera core."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "⚙️ Configuration"
    )

    st.subheader(
        "AI Provider"
    )

    provider = st.radio(

        "Choose testing mode",

        [
            "Core Only",
            "OpenAI",
        ],

        index=0,
    )


    # --------------------------------------------------------
    # OpenAI settings
    # --------------------------------------------------------

    if provider == "OpenAI":

        st.divider()

        st.subheader(
            "OpenAI Settings"
        )


        openai_api_key = st.text_input(

            "OpenAI API Key",

            value=get_secret_or_env(
                "OPENAI_API_KEY"
            ),

            type="password",

            help=(
                "For deployment, store this "
                "in Streamlit Secrets instead "
                "of hard-coding it."
            ),
        )


        openai_model = st.text_input(

            "Model",

            value=get_secret_or_env(
                "OPENAI_MODEL"
            ) or DEFAULT_OPENAI_MODEL,
        )


        if OPENAI_AVAILABLE:

            st.success(
                "OpenAI SDK detected."
            )

        else:

            st.error(
                "OpenAI SDK not detected."
            )

            st.code(
                str(
                    OPENAI_IMPORT_ERROR
                ),
                language="text",
            )


    # --------------------------------------------------------
    # Core-only mode
    # --------------------------------------------------------

    else:

        st.info(
            "Core Only mode directly tests "
            "bot.compose()."
        )


# ============================================================
# PROJECT STATUS
# ============================================================

st.divider()

st.subheader(
    "System Status"
)

s1, s2, s3, s4 = st.columns(4)

with s1:
    st.metric(
        "Categories",
        len(categories),
    )

with s2:
    st.metric(
        "Merchants",
        len(merchants),
    )

with s3:
    st.metric(
        "Customers",
        len(customers),
    )

with s4:
    st.metric(
        "Triggers",
        len(triggers),
    )


if VERA_AVAILABLE:

    st.success(
        "✅ Vera core loaded successfully."
    )

else:

    st.error(
        "❌ Vera core could not be imported."
    )

    st.code(
        str(
            VERA_IMPORT_ERROR
        ),
        language="text",
    )

    st.stop()


# ============================================================
# MAIN TABS
# ============================================================

tab_dataset, tab_custom = st.tabs(
    [
        "🧪 Dataset Test",
        "🛠️ Custom JSON Test",
    ]
)


# ============================================================
# TAB 1 — DATASET TEST
# ============================================================

with tab_dataset:

    st.header(
        "Test Vera with the real dataset"
    )

    if not categories:

        st.error(
            "No files found in dataset/categories/"
        )

        st.stop()


    if not merchants:

        st.error(
            "No files found in dataset/merchants/"
        )

        st.stop()


    if not triggers:

        st.error(
            "No files found in dataset/triggers/"
        )

        st.stop()


    # ========================================================
    # CATEGORY
    # ========================================================

    category_index = st.selectbox(

        "1. Select Category",

        options=range(
            len(categories)
        ),

        format_func=lambda i:
        get_label(
            categories[i],
            "category",
        ),
    )

    selected_category = unwrap(
        categories[
            category_index
        ]
    )


            # ========================================================
        # MERCHANT
        # ========================================================

    selected_category_slug = selected_category.get(
            "slug"
        )

    category_merchants = []

    for merchant_record in merchants:

        merchant_data = unwrap(
                merchant_record
            )

        merchant_category_slug = merchant_data.get(
                "category_slug"
            )

        if (
                selected_category_slug is not None
                and merchant_category_slug == selected_category_slug
            ):
                category_merchants.append(
                    merchant_record
                )


    if not category_merchants:

            st.error(
                f"No merchants found for category "
                f"'{selected_category_slug}'."
            )

            st.stop()


    merchant_index = st.selectbox(

            "2. Select Merchant",

            options=range(
                len(category_merchants)
            ),

            format_func=lambda i:
            get_label(
                category_merchants[i],
                "merchant",
            ),
        )


    selected_merchant = unwrap(
            category_merchants[
                merchant_index
            ]
        )


    selected_merchant_id = get_id(
            selected_merchant,
            "merchant",
        )


        # Extra safety check
    if (
            selected_merchant.get("category_slug")
            != selected_category_slug
        ):

            st.error(
                "Selected merchant does not belong to "
                "the selected category."
            )

            st.stop()



    # ========================================================
    # TRIGGER FILTERING
    # ========================================================

    matching_triggers = []

    for trigger_record in triggers:

        trigger = unwrap(
            trigger_record
        )

        trigger_merchant_id = (
            get_trigger_merchant_id(
                trigger
            )
        )

        if (
            trigger_merchant_id is not None
            and str(trigger_merchant_id)
            == str(selected_merchant_id)
        ):

            matching_triggers.append(
                trigger_record
            )


    trigger_options = (
        matching_triggers
        if matching_triggers
        else triggers
    )


    if matching_triggers:

        st.info(
            f"Found {len(matching_triggers)} "
            "trigger(s) for this merchant."
        )

    else:

        st.warning(
            "No merchant-specific trigger was found. "
            "All triggers are shown."
        )


    # ========================================================
    # TRIGGER
    # ========================================================

    trigger_index = st.selectbox(

        "3. Select Trigger",

        options=range(
            len(trigger_options)
        ),

        format_func=lambda i:
        get_label(
            trigger_options[i],
            "trigger",
        ),
    )

    selected_trigger = unwrap(
        trigger_options[
            trigger_index
        ]
    )


    # ========================================================
    # CUSTOMER
    # ========================================================

    trigger_customer_id = (
        get_trigger_customer_id(
            selected_trigger
        )
    )


    matching_customers = []

    for customer_record in customers:

        customer = unwrap(
            customer_record
        )

        customer_id = get_id(
            customer,
            "customer",
        )

        customer_merchant_id = (
            get_customer_merchant_id(
                customer
            )
        )


        # Explicit customer from trigger
        if trigger_customer_id:

            if (
                str(customer_id)
                == str(trigger_customer_id)
            ):

                matching_customers.append(
                    customer_record
                )


        # Otherwise filter by merchant
        elif customer_merchant_id:

            if (
                str(customer_merchant_id)
                == str(selected_merchant_id)
            ):

                matching_customers.append(
                    customer_record
                )


    st.markdown(
        "### 4. Customer"
    )


    customer_mode = st.radio(

        "Customer mode",

        [
            "No customer",
            "Select customer",
        ],

        horizontal=True,
    )


    selected_customer = None


    if customer_mode == "Select customer":

        customer_options = (
            matching_customers
            if matching_customers
            else customers
        )


        if customer_options:

            customer_index = st.selectbox(

                "Select Customer",

                options=range(
                    len(customer_options)
                ),

                format_func=lambda i:
                get_label(
                    customer_options[i],
                    "customer",
                ),
            )


            selected_customer = unwrap(
                customer_options[
                    customer_index
                ]
            )

        else:

            st.warning(
                "No customers available."
            )


    # ========================================================
    # INPUT PREVIEW
    # ========================================================

    st.divider()

    st.header(
        "📦 Input Context"
    )


    col_a, col_b = st.columns(2)


    with col_a:

        with st.expander(
            "Category JSON"
        ):

            st.json(
                selected_category
            )


        with st.expander(
            "Merchant JSON"
        ):

            st.json(
                selected_merchant
            )


    with col_b:

        with st.expander(
            "Trigger JSON"
        ):

            st.json(
                selected_trigger
            )


        with st.expander(
            "Customer JSON"
        ):

            if selected_customer is None:

                st.write(
                    "None"
                )

            else:

                st.json(
                    selected_customer
                )


    # ========================================================
    # RUN
    # ========================================================

    st.divider()

    run_button = st.button(

        "▶ Run Vera",

        type="primary",

        use_container_width=True,
    )


    if run_button:

        # ====================================================
        # STEP 1 — CORE
        # ====================================================

        try:

            with st.spinner(
                "Running Vera core..."
            ):

                core_result = vera_compose(

                    selected_category,

                    selected_merchant,

                    selected_trigger,

                    selected_customer,
                )


                core_result = normalize_result(
                    core_result
                )


        except Exception as exc:

            st.error(
                "Vera core raised an exception."
            )

            st.exception(
                exc
            )

            st.stop()


        st.success(
            "✅ Vera core completed."
        )


        # ====================================================
        # CORE OUTPUT
        # ====================================================

        st.header(
            "🧠 Vera Core Output"
        )


        st.markdown(
            "### 💬 Message"
        )

        st.info(
            core_result.get(
                "body",
                "",
            )
        )


        core_a, core_b, core_c = st.columns(3)


        with core_a:

            st.metric(
                "CTA",
                str(
                    core_result.get(
                        "cta",
                        "",
                    )
                ),
            )


        with core_b:

            st.metric(
                "Send As",
                str(
                    core_result.get(
                        "send_as",
                        "",
                    )
                ),
            )


        with core_c:

            st.metric(
                "Body Length",
                len(
                    str(
                        core_result.get(
                            "body",
                            "",
                        )
                    )
                ),
            )


        with st.expander(
            "Complete Core JSON"
        ):

            st.json(
                core_result
            )


        # ====================================================
        # OPENAI
        # ====================================================

        if provider == "OpenAI":

            st.divider()

            st.header(
                "✨ OpenAI Refined Output"
            )


            if not openai_api_key.strip():

                st.warning(
                    "Enter your OpenAI API key "
                    "in the sidebar."
                )

            else:

                prompt = build_openai_prompt(

                    selected_category,

                    selected_merchant,

                    selected_trigger,

                    selected_customer,

                    core_result,
                )


                try:

                    with st.spinner(
                        f"Generating with {openai_model}..."
                    ):

                        ai_result = call_openai(

                            api_key=openai_api_key,

                            model=openai_model,

                            prompt=prompt,
                        )


                    final_result = merge_openai_result(

                        core_result,

                        ai_result,
                    )


                    st.success(
                        "✅ OpenAI generation completed."
                    )


                    st.markdown(
                        "### 💬 Final AI Message"
                    )


                    st.info(
                        final_result.get(
                            "body",
                            "",
                        )
                    )


                    ai_a, ai_b, ai_c = st.columns(3)


                    with ai_a:

                        st.metric(
                            "CTA",
                            str(
                                final_result.get(
                                    "cta",
                                    "",
                                )
                            ),
                        )


                    with ai_b:

                        st.metric(
                            "Send As",
                            str(
                                final_result.get(
                                    "send_as",
                                    "",
                                )
                            ),
                        )


                    with ai_c:

                        st.metric(
                            "Body Length",
                            len(
                                str(
                                    final_result.get(
                                        "body",
                                        "",
                                    )
                                )
                            ),
                        )


                    # =================================================
                    # AI RATIONALE
                    # =================================================

                    st.markdown(
                        "### 🧠 AI Rationale"
                    )

                    st.write(
                        final_result.get(
                            "rationale",
                            "",
                        )
                    )


                    # =================================================
                    # CONTROLLED FIELDS
                    # =================================================

                    st.markdown(
                        "### 🔐 Core-Controlled Fields"
                    )

                    st.write(
                        "The following fields remain controlled "
                        "by Vera core:"
                    )

                    st.code(
                        json.dumps(
                            {
                                "send_as": final_result.get(
                                    "send_as",
                                    "",
                                ),
                                "suppression_key": final_result.get(
                                    "suppression_key",
                                    "",
                                ),
                            },
                            indent=2,
                        ),
                        language="json",
                    )


                    # =================================================
                    # FINAL JSON
                    # =================================================

                    with st.expander(
                        "Complete Final JSON"
                    ):

                        st.json(
                            final_result
                        )


                    # =================================================
                    # COMPARISON
                    # =================================================

                    st.divider()

                    st.header(
                        "🔍 Core vs OpenAI"
                    )


                    comparison_data = [

                        {
                            "Field": "body",
                            "Core": core_result.get(
                                "body",
                                "",
                            ),
                            "OpenAI": final_result.get(
                                "body",
                                "",
                            ),
                        },

                        {
                            "Field": "cta",
                            "Core": core_result.get(
                                "cta",
                                "",
                            ),
                            "OpenAI": final_result.get(
                                "cta",
                                "",
                            ),
                        },

                        {
                            "Field": "send_as",
                            "Core": core_result.get(
                                "send_as",
                                "",
                            ),
                            "OpenAI": final_result.get(
                                "send_as",
                                "",
                            ),
                        },

                        {
                            "Field": "suppression_key",
                            "Core": core_result.get(
                                "suppression_key",
                                "",
                            ),
                            "OpenAI": final_result.get(
                                "suppression_key",
                                "",
                            ),
                        },

                        {
                            "Field": "rationale",
                            "Core": core_result.get(
                                "rationale",
                                "",
                            ),
                            "OpenAI": final_result.get(
                                "rationale",
                                "",
                            ),
                        },
                    ]


                    st.dataframe(

                        comparison_data,

                        use_container_width=True,

                        hide_index=True,
                    )


                except json.JSONDecodeError:

                    st.error(
                        "OpenAI returned invalid JSON."
                    )

                except Exception as exc:

                    st.error(
                        "OpenAI generation failed."
                    )

                    st.exception(
                        exc
                    )


# ============================================================
# TAB 2 — CUSTOM JSON TEST
# ============================================================

with tab_custom:

    st.header(
        "🛠️ Custom JSON Test"
    )

    st.write(
        "Use this to test new or modified contexts "
        "without changing the original dataset."
    )


    default_category = (
        unwrap(categories[0])
        if categories
        else {}
    )


    default_merchant = (
        unwrap(merchants[0])
        if merchants
        else {}
    )


    default_trigger = (
        unwrap(triggers[0])
        if triggers
        else {}
    )


    category_text = st.text_area(

        "Category JSON",

        value=json.dumps(
            default_category,
            indent=2,
            ensure_ascii=False,
        ),

        height=280,
    )


    merchant_text = st.text_area(

        "Merchant JSON",

        value=json.dumps(
            default_merchant,
            indent=2,
            ensure_ascii=False,
        ),

        height=280,
    )


    trigger_text = st.text_area(

        "Trigger JSON",

        value=json.dumps(
            default_trigger,
            indent=2,
            ensure_ascii=False,
        ),

        height=280,
    )


    customer_text = st.text_area(

        "Customer JSON",

        value="",

        height=220,

        placeholder=(
            "Leave empty when there is no customer."
        ),
    )


    st.divider()


    run_custom = st.button(

        "▶ Run Custom Vera",

        type="primary",

        use_container_width=True,
    )


    if run_custom:

        # ====================================================
        # PARSE JSON
        # ====================================================

        try:

            custom_category = json.loads(
                category_text
            )

            custom_merchant = json.loads(
                merchant_text
            )

            custom_trigger = json.loads(
                trigger_text
            )


            if customer_text.strip():

                custom_customer = json.loads(
                    customer_text
                )

            else:

                custom_customer = None


        except json.JSONDecodeError as exc:

            st.error(
                "Invalid JSON."
            )

            st.exception(
                exc
            )

            st.stop()


        # ====================================================
        # CORE
        # ====================================================

        try:

            with st.spinner(
                "Running Vera core..."
            ):

                custom_core = vera_compose(

                    custom_category,

                    custom_merchant,

                    custom_trigger,

                    custom_customer,
                )


                custom_core = normalize_result(
                    custom_core
                )


            st.success(
                "✅ Custom Vera test completed."
            )


        except Exception as exc:

            st.error(
                "Vera core failed."
            )

            st.exception(
                exc
            )

            st.stop()


        # ====================================================
        # DISPLAY CORE
        # ====================================================

        st.subheader(
            "🧠 Core Output"
        )


        st.info(
            custom_core.get(
                "body",
                "",
            )
        )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "CTA",
                str(
                    custom_core.get(
                        "cta",
                        "",
                    )
                ),
            )


        with c2:

            st.metric(
                "Send As",
                str(
                    custom_core.get(
                        "send_as",
                        "",
                    )
                ),
            )


        with c3:

            st.metric(
                "Body Length",
                len(
                    str(
                        custom_core.get(
                            "body",
                            "",
                        )
                    )
                ),
            )


        with st.expander(
            "Complete Core JSON"
        ):

            st.json(
                custom_core
            )


        # ====================================================
        # OPENAI CUSTOM
        # ====================================================

        if provider == "OpenAI":

            st.divider()

            st.subheader(
                "✨ OpenAI Refined Output"
            )


            if not openai_api_key.strip():

                st.warning(
                    "Enter your OpenAI API key "
                    "in the sidebar."
                )

            else:

                custom_prompt = build_openai_prompt(

                    custom_category,

                    custom_merchant,

                    custom_trigger,

                    custom_customer,

                    custom_core,
                )


                try:

                    with st.spinner(
                        f"Generating with {openai_model}..."
                    ):

                        custom_ai = call_openai(

                            api_key=openai_api_key,

                            model=openai_model,

                            prompt=custom_prompt,
                        )


                    custom_final = merge_openai_result(

                        custom_core,

                        custom_ai,
                    )


                    st.success(
                        "✅ OpenAI generation completed."
                    )


                    st.info(
                        custom_final.get(
                            "body",
                            "",
                        )
                    )


                    with st.expander(
                        "Complete Final JSON"
                    ):

                        st.json(
                            custom_final
                        )


                except Exception as exc:

                    st.error(
                        "OpenAI generation failed."
                    )

                    st.exception(
                        exc )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Vera Core Tester • Streamlit • "
    "Deterministic Core + OpenAI"
)