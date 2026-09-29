import streamlit as st
from supabase import create_client, Client

st.set_page_config(
    page_title="Household Info Vault",
    page_icon="🔐",
    layout="wide",
)

CATEGORIES = ["WiFi", "Utilities", "Appliances", "Documents", "Contacts"]


@st.cache_resource
def get_supabase_client() -> Client:
    """Connect to Supabase using secrets stored in .streamlit/secrets.toml."""
    if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
        st.error("Missing SUPABASE_URL or SUPABASE_KEY in .streamlit/secrets.toml")
        st.stop()

    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    try:
        return create_client(url, key)
    except Exception:
        st.error("Failed to initialize Supabase client. Please check your credentials.")
        st.stop()


def check_password() -> bool:
    """Returns True if the user is authenticated, otherwise displays password input."""
    if st.session_state.get("authenticated", False) or st.session_state.get("password_correct", False):
        return True

    if "APP_PASSWORD" not in st.secrets:
        st.error("Missing APP_PASSWORD in .streamlit/secrets.toml")
        return False

    password = st.text_input("Password", type="password", key="password_input")
    submit = st.button("Log In", key="login_button")

    if submit:
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state["authenticated"] = True
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


def main():
    # Require password authentication before rendering any content
    if not check_password():
        return

    st.title("🔐 Household Info Vault")

    client = get_supabase_client()

    if "editing_item_id" not in st.session_state:
        st.session_state.editing_item_id = None
    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None

    # Form to add a new item
    with st.form("add_item_form", clear_on_submit=True):
        st.subheader("Add New Item")
        category = st.selectbox("Category", options=CATEGORIES, key="add_category")
        title = st.text_input("Title", key="add_title")
        value = st.text_input("Value", key="add_value")
        note = st.text_input("Note", key="add_note")
        submitted = st.form_submit_button("Add Item")

        if submitted:
            if not title or not title.strip():
                st.error("Title is required.")
            else:
                try:
                    payload = {
                        "category": category,
                        "title": title.strip(),
                        "value": value.strip() if value else "",
                        "note": note.strip() if note else "",
                    }
                    client.table("items").insert(payload).execute()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error adding item: {exc}")

    # Category filter dropdown with exactly the 5 fixed options
    selected_category = st.selectbox(
        "Category",
        options=CATEGORIES,
        index=None,
        placeholder="All categories",
        key="filter_category",
    )

    # Text search box to filter by title, value, or note
    search_query = st.text_input("Search", key="search_query")

    # Fetch items from Supabase
    try:
        query = client.table("items").select("id, category, title, value, note").order("id")
        if selected_category:
            query = query.eq("category", selected_category)

        response = query.execute()
        items = response.data or []
    except Exception as exc:
        st.error(f"Error fetching items: {exc}")
        return

    # Filter items by search text (case-insensitive across title, value, or note)
    if search_query:
        term = search_query.strip().lower()
        if term:
            items = [
                item
                for item in items
                if term in (item.get("title") or "").lower()
                or term in (item.get("value") or "").lower()
                or term in (item.get("note") or "").lower()
            ]

    # Display items
    if items:
        col_id, col_cat, col_title, col_val, col_note, col_actions = st.columns(
            [0.8, 1.5, 2, 2, 2.5, 2]
        )
        with col_id:
            st.markdown("**ID**")
        with col_cat:
            st.markdown("**Category**")
        with col_title:
            st.markdown("**Title**")
        with col_val:
            st.markdown("**Value**")
        with col_note:
            st.markdown("**Note**")
        with col_actions:
            st.markdown("**Actions**")
        st.divider()

        for item in items:
            item_id = item["id"]

            if st.session_state.editing_item_id == item_id:
                with st.container(border=True):
                    st.markdown(f"**Edit Item #{item_id}**")
                    with st.form(f"edit_form_{item_id}"):
                        current_cat = item.get("category")
                        cat_index = (
                            CATEGORIES.index(current_cat) if current_cat in CATEGORIES else 0
                        )
                        edit_category = st.selectbox(
                            "Category",
                            options=CATEGORIES,
                            index=cat_index,
                            key=f"edit_cat_{item_id}",
                        )
                        edit_title = st.text_input(
                            "Title",
                            value=item.get("title") or "",
                            key=f"edit_title_{item_id}",
                        )
                        edit_value = st.text_input(
                            "Value",
                            value=item.get("value") or "",
                            key=f"edit_value_{item_id}",
                        )
                        edit_note = st.text_input(
                            "Note",
                            value=item.get("note") or "",
                            key=f"edit_note_{item_id}",
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            save_clicked = st.form_submit_button("Save", use_container_width=True)
                        with col_cancel:
                            cancel_clicked = st.form_submit_button(
                                "Cancel", use_container_width=True
                            )

                        if save_clicked:
                            if not edit_title or not edit_title.strip():
                                st.error("Title is required.")
                            else:
                                try:
                                    payload = {
                                        "category": edit_category,
                                        "title": edit_title.strip(),
                                        "value": edit_value.strip() if edit_value else "",
                                        "note": edit_note.strip() if edit_note else "",
                                    }
                                    client.table("items").update(payload).eq("id", item_id).execute()
                                    st.session_state.editing_item_id = None
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Error updating item: {exc}")

                        if cancel_clicked:
                            st.session_state.editing_item_id = None
                            st.rerun()

            elif st.session_state.confirm_delete_id == item_id:
                with st.container(border=True):
                    st.warning(f"Are you sure you want to delete **'{item.get('title')}'**?")
                    col_del_confirm, col_del_cancel = st.columns(2)
                    with col_del_confirm:
                        if st.button(
                            "Confirm Delete",
                            key=f"confirm_delete_{item_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                client.table("items").delete().eq("id", item_id).execute()
                                st.session_state.confirm_delete_id = None
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Error deleting item: {exc}")
                    with col_del_cancel:
                        if st.button(
                            "Cancel", key=f"cancel_delete_{item_id}", use_container_width=True
                        ):
                            st.session_state.confirm_delete_id = None
                            st.rerun()

            else:
                col_id, col_cat, col_title, col_val, col_note, col_actions = st.columns(
                    [0.8, 1.5, 2, 2, 2.5, 2]
                )
                with col_id:
                    st.write(str(item_id))
                with col_cat:
                    st.write(item.get("category") or "")
                with col_title:
                    st.write(item.get("title") or "")
                with col_val:
                    st.write(item.get("value") or "")
                with col_note:
                    st.write(item.get("note") or "")
                with col_actions:
                    col_btn_edit, col_btn_del = st.columns(2)
                    with col_btn_edit:
                        if st.button("Edit", key=f"edit_btn_{item_id}", use_container_width=True):
                            st.session_state.editing_item_id = item_id
                            st.session_state.confirm_delete_id = None
                            st.rerun()
                    with col_btn_del:
                        if st.button(
                            "Delete", key=f"delete_btn_{item_id}", use_container_width=True
                        ):
                            st.session_state.confirm_delete_id = item_id
                            st.session_state.editing_item_id = None
                            st.rerun()
            st.divider()
    else:
        st.info("No items found.")


if __name__ == "__main__":
    main()
