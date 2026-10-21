"""Manage reusable AEM environments and website mappings."""

import uuid
from urllib.parse import urlsplit

import pandas as pd
import streamlit as st

from modules.config_manager import load, save, valid_author
from modules.aem_auth import (
    token_status,
    save_token,
    delete_token,
)

st.set_page_config(
    page_title="Global AEM Settings",
    layout="wide"
)

st.title("Global AEM Settings")

envs = load("aem_environments.json", "environments")
mappings = load("aem_mappings.json", "mappings")

tab1, tab2 = st.tabs([
    "AEM Environments",
    "Website Mappings"
])

with tab1:
    st.subheader("AEM Environments")

    if envs:
        st.dataframe(
            pd.DataFrame(envs),
            width="stretch"
        )

    with st.form("new_environment"):
        name = st.text_input("Environment Name")
        author = st.text_input(
            "Author Base URL",
            placeholder="https://author.example.com"
        )
        create = st.form_submit_button("Add Environment")

    if create:
        if not name.strip() or not valid_author(author):
            st.error("Enter a name and valid HTTPS Author URL.")
        elif any(
            e["author_base"] == author.rstrip("/")
            for e in envs
        ):
            st.error("Environment already exists.")
        else:
            envs.append({
                "id": "env_" + uuid.uuid4().hex[:12],
                "name": name.strip(),
                "author_base": author.rstrip("/")
            })
            save("aem_environments.json", "environments", envs)
            st.rerun()

    if envs:
        st.divider()
        index = st.selectbox(
            "Manage Environment",
            range(len(envs)),
            format_func=lambda i: envs[i]["name"]
        )

        env = envs[index]
        auth = token_status(env)

        st.info(auth["message"])

        with st.form("edit_environment"):
            edit_name = st.text_input(
                "Name", value=env["name"]
            )
            edit_author = st.text_input(
                "Author URL", value=env["author_base"]
            )
            update = st.form_submit_button(
                "Save Environment"
            )

        if update:
            if not edit_name.strip() or not valid_author(edit_author):
                st.error("Invalid environment details.")
            elif any(
                i != index and
                e["author_base"] == edit_author.rstrip("/")
                for i, e in enumerate(envs)
            ):
                st.error("Author URL already configured.")
            else:
                env.update(
                    name=edit_name.strip(),
                    author_base=edit_author.rstrip("/")
                )
                save("aem_environments.json", "environments", envs)
                st.rerun()

        with st.form("environment_token"):
            token = st.text_input(
                "Bearer Token",
                type="password"
            )
            store = st.form_submit_button(
                "Save / Replace Token"
            )

        if store:
            try:
                save_token(env, token)
                st.success("Token stored in OS credential vault.")
            except Exception as exc:
                st.error(
                    "Credential storage failed: "
                    + type(exc).__name__
                )

        if st.button("Remove Token"):
            try:
                delete_token(env)
                st.rerun()
            except Exception as exc:
                st.error(type(exc).__name__)

        if st.button("Delete Environment"):
            if any(
                m["environment_id"] == env["id"]
                for m in mappings
            ):
                st.error(
                    "Remove associated website mappings first."
                )
            elif auth["status"] not in ("missing", "unavailable"):
                st.error("Remove the stored token first.")
            else:
                envs.pop(index)
                save("aem_environments.json", "environments", envs)
                st.rerun()

with tab2:
    st.subheader("Website Mappings")

    if mappings:
        st.dataframe(
            pd.DataFrame(mappings),
            width="stretch"
        )

    if not envs:
        st.warning("Create an AEM environment first.")
    else:
        options = {
            e["id"]: e["name"]
            for e in envs
        }

        with st.form("new_mapping"):
            name = st.text_input("Website Name")
            domain = st.text_input(
                "Published Domain",
                placeholder="www.example.com"
            )
            prefix = st.text_input(
                "Published Prefix", value="/en"
            )
            content_root = st.text_input(
                "AEM Content Root",
                placeholder="/content/example/en"
            )
            environment_id = st.selectbox(
                "AEM Environment",
                list(options),
                format_func=lambda x: options[x]
            )
            create = st.form_submit_button("Add Mapping")

        if create:
            domain = domain.strip().lower()
            prefix = prefix.rstrip("/") or "/"
            content_root = content_root.rstrip("/")

            parsed = urlsplit("https://" + domain)

            valid = (
                bool(name.strip())
                and bool(domain)
                and parsed.hostname == domain
                and parsed.port is None
                and prefix.startswith("/")
                and content_root.startswith("/content/")
                and ".." not in prefix.split("/")
                and ".." not in content_root.split("/")
            )

            duplicate = any(
                m["published_domain"].lower() == domain
                and m["published_prefix"] == prefix
                for m in mappings
            )

            if not valid:
                st.error("Invalid website mapping.")
            elif duplicate:
                st.error("Mapping already exists.")
            else:
                mappings.append({
                    "name": name.strip(),
                    "published_domain": domain,
                    "published_prefix": prefix,
                    "content_root": content_root,
                    "environment_id": environment_id
                })
                save("aem_mappings.json", "mappings", mappings)
                st.rerun()

        if mappings:
            st.divider()
            index = st.selectbox(
                "Manage Mapping",
                range(len(mappings)),
                format_func=lambda i: mappings[i]["name"]
            )
            selected = mappings[index]

            with st.form("edit_mapping"):
                edit_name = st.text_input(
                    "Name", selected["name"]
                )
                edit_domain = st.text_input(
                    "Domain", selected["published_domain"]
                )
                edit_prefix = st.text_input(
                    "Prefix", selected["published_prefix"]
                )
                edit_root = st.text_input(
                    "Content Root", selected["content_root"]
                )
                current_id = selected["environment_id"]
                env_ids = list(options)
                edit_env = st.selectbox(
                    "Environment",
                    env_ids,
                    index=(
                        env_ids.index(current_id)
                        if current_id in env_ids else 0
                    ),
                    format_func=lambda x: options[x]
                )
                update = st.form_submit_button("Save Mapping")

            if update:
                edit_domain = edit_domain.strip().lower()
                edit_prefix = edit_prefix.rstrip("/") or "/"
                edit_root = edit_root.rstrip("/")

                parsed = urlsplit("https://" + edit_domain)
                valid = (
                    bool(edit_name.strip())
                    and parsed.hostname == edit_domain
                    and parsed.port is None
                    and edit_prefix.startswith("/")
                    and edit_root.startswith("/content/")
                    and ".." not in edit_prefix.split("/")
                    and ".." not in edit_root.split("/")
                )
                duplicate = any(
                    i != index
                    and m["published_domain"].lower() == edit_domain
                    and m["published_prefix"] == edit_prefix
                    for i, m in enumerate(mappings)
                )

                if not valid or duplicate:
                    st.error("Invalid or duplicate mapping.")
                else:
                    selected.update(
                        name=edit_name.strip(),
                        published_domain=edit_domain,
                        published_prefix=edit_prefix,
                        content_root=edit_root,
                        environment_id=edit_env
                    )
                    save("aem_mappings.json", "mappings", mappings)
                    st.rerun()

            if st.button("Delete Mapping"):
                mappings.pop(index)
                save("aem_mappings.json", "mappings", mappings)
                st.rerun()
