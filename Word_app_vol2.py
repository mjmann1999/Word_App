#!/usr/bin/env python
# coding: utf-8

# In[2]:


import itertools
import streamlit as st

def load_words(file_path):
    with open(file_path, 'r') as f:
        words = [word.lower() for word in f.read().splitlines()]
    return words

sowpods_words = set(load_words("C:\\Users\\mjman\\Downloads\\sowpods.txt"))

def all_words(letters, include_letters="", exclude_letters="", min_length=1, max_length=None):
    """Returns a list of all the English words possible from a set of letters."""
    generated_words = []
    max_length = max_length or len(letters)
    for i in range(min_length, max_length + 1):
        for permutation in itertools.permutations(letters.lower(), i):
            word = "".join(permutation)
            if word in sowpods_words and all(letter in word for letter in include_letters) and not any(letter in word for letter in exclude_letters):
                generated_words.append(word)
    return sorted(generated_words, key=len, reverse=True)

def main():
    st.title("English Word Generator")

    # Instructions
    st.markdown("""
    This application finds all possible English words from the provided letters.
    You can customize the minimum and maximum length of the words, include or exclude specific letters.
    """)

    # User input
    letters = st.text_input("Enter the letters you want to generate words from:", "abcdefgh").strip()
    min_length = st.slider('Minimum length of words', 1, len(letters), 1)
    max_length = st.slider('Maximum length of words', min_length, len(letters), len(letters))
    include_letters = st.text_input("Letters to include (optional):").strip()
    exclude_letters = st.text_input("Letters to exclude (optional):").strip()

    # Validate input
    if not all((x.isalpha() or x == "") for x in [letters, include_letters, exclude_letters]):
        st.error('Please enter only English letters.')
    else:
        # Generate words
        with st.spinner('Generating words...'):
            generated_words = all_words(letters, include_letters, exclude_letters, min_length, max_length)

        # Display results
        st.write(f"The following {len(generated_words)} English words can be formed from the letters '{letters}':")

        # Use columns to display the words
        cols = st.columns(2)
        for i, word in enumerate(generated_words):
            cols[i % 2].markdown(f"- {word}")

if __name__ == "__main__":
    main()

