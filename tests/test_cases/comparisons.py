"""Comparison query test cases."""
from .base import TestCase, contains_all_substrings, min_length

COMPARISON_TESTS = [
    # ... previous comparison_directors case ...
    TestCase(
        name="comparison_animation_studios",
        prompt="Compare the storytelling and animation philosophies of Pixar and Studio Ghibli.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("pixar", "ghibli", "cgi", "hand-drawn", "miyazaki", "story"),
            min_length(200)
        ]
    ),
    TestCase(
        name="comparison_horror_directors",
        prompt="Contrast the suspense techniques of Alfred Hitchcock and M. Night Shyamalan.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("hitchcock", "shyamalan", "suspense", "twist", "master", "cinematography"),
            min_length(150)
        ]
    ),
    TestCase(
        name="comparison_superhero_universes",
        prompt="What are the stylistic differences between the Marvel Cinematic Universe (MCU) and the DC Extended Universe (DCEU)?",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("marvel", "mcu", "dc", "dceu", "tone", "color", "cinematic"),
            min_length(150)
        ]
    ),
    TestCase(
        name="comparison_crime_auteurs",
        prompt="Compare how Martin Scorsese and Quentin Tarantino use dialogue and violence in their crime films.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("scorsese", "tarantino", "dialogue", "violence", "stylized", "realistic"),
            min_length(200)
        ]
    ),
    TestCase(
        name="comparison_female_auteurs",
        prompt="Compare the directorial lens of Greta Gerwig and Sofia Coppola regarding femininity and isolation.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("gerwig", "coppola", "femininity", "isolation", "aesthetic", "perspective"),
            min_length(150)
        ]
    ),
    TestCase(
        name="comparison_sci_fi_eras",
        prompt="Compare 1970s science fiction cinema to the blockbusters of the 2010s in terms of visual effects and themes.",
        expected_type="comparison",
        acceptance_criteria=[
            contains_all_substrings("70s", "2010s", "practical effects", "cgi", "themes", "blockbuster"),
            min_length(150)
        ]
    )
]
