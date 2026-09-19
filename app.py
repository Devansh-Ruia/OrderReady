"""Devansh owns this file. Ugly is fine before 1:15. Style nothing until 2:45."""
import json
import streamlit as st
from model import extract_order, FIELDS
from order_logic import validate, render_ticket, ticket_json, SIZES, LABEL

st.set_page_config(page_title="OrderReady", layout="wide")
st.title("OrderReady")
st.caption("Intake for a one-person T-shirt shop. All inquiries here are synthetic.")

if "ex" not in st.session_state:
    st.session_state.ex = None

text = st.text_area("Paste the customer inquiry", height=160, key="inq")

if st.button("Read inquiry", type="primary"):
    if text.strip():
        with st.spinner("Reading…"):
            st.session_state.ex = extract_order(text)

ex = st.session_state.ex
if ex:
    if ex["error"]:
        st.error(f"Live AI unavailable — manual intake mode. ({ex['error']})")

    left, right = st.columns(2)

    with left:
        st.subheader("What the inquiry actually says")
        for name in FIELDS:
            f = ex["fields"][name]
            label = LABEL.get(name, name.replace("_", " "))
            if f["value"] is not None:
                st.markdown(f"**{label}** — `{f['value']}`")
                st.caption(f'from: "{f["evidence"]}"')
            else:
                shown = f'"{f["evidence"]}" — not specific enough' if f["evidence"] else "not stated"
                st.markdown(f"**{label}** — :red[missing]")
                st.caption(shown)

    with right:
        st.subheader("Fill the gaps")
        ov = {}
        if ex["fields"]["customer_name"]["value"] is None:
            ov["customer_name"] = st.text_input("Customer name")
        if ex["fields"]["contact"]["value"] is None:
            ov["contact"] = st.text_input("Email or phone")
        if ex["fields"]["sizes"]["value"] is None:
            c = st.columns(3)
            counts = {s: c[i].number_input(s, 0, 999, 0) for i, s in enumerate(SIZES)}
            if sum(counts.values()) > 0:
                ov["sizes"] = counts
        if ex["fields"]["deadline"]["value"] is None:
            d = st.date_input("Deadline", value=None)
            if d:
                ov["deadline"] = d.isoformat()

    res = validate(ex, ov)

    for q in res["questions"]:
        st.warning(f"Ask the customer: {q}")
    for b in res["blocks"]:
        st.error(b)
    if res["missing"]:
        st.info("Still needed: " + ", ".join(res["missing"]))

    st.divider()
    if res["ok"]:
        ticket = render_ticket(res)
        st.code(ticket)
        a, b = st.columns(2)
        a.download_button("Export ticket (.txt)", ticket, "intake-ticket.txt")
        b.download_button("Export ticket (.json)",
                          json.dumps(ticket_json(res), indent=2), "intake-ticket.json")
    else:
        st.button("Export ticket", disabled=True,
                  help="Blocked until every required field is present and the totals agree.")
