import streamlit as st

st.title("Test page")
st.write("If you can see this, Streamlit is working fine.")

if st.button("Click me"):
    st.write("Button works too!")