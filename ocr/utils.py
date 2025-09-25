from spellchecker import SpellChecker

spell = SpellChecker(language="en")

def correct_word(word: str) -> str:
    # Ignore single letters or numbers
    if len(word) <= 1 or word.isdigit():
        return word

    corrected = spell.correction(word.lower())
    if not corrected:
        return word

    # Preserve capitalization
    if word[0].isupper():
        corrected = corrected.capitalize()

    return corrected