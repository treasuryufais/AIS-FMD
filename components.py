import streamlit as st 
import time 


def animated_typing_title(text, delay=0.02, font_size="42px", color="#FFFFFF"):
    """
    Display the provided text with a typing animation.
    """
    placeholder = st.empty()
    full_text = ""
    for char in text:
        full_text += char
        placeholder.markdown(
            f"<h1 style='color:{color}; font-size: {font_size}; margin: 0'>{full_text}</h1>",
            unsafe_allow_html=True,
        )
        time.sleep(delay)

def apply_nav_title():
    """
    Injects custom CSS to replace Streamlit's default Pages header with your own title.

    Call this at the top of every page script to ensure the navigation title is rendered.
    """
    css = f"""
    <style>
      /* Hide default "Pages" header */
      div[data-testid="stSidebarNav"] > div:first-child {{
        display: none;
      }}
      /* Insert custom title */
      div[data-testid="stSidebarNav"]::before {{
        content: "Navigation";
        display: block;
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
        padding: 0 1rem;
        text-align: center;
      }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)