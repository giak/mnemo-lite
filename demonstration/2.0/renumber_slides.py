#!/usr/bin/env python3
"""
Script pour renuméroter les slides après avoir déplacé la section "A quoi ça sert?"

Nouvelle structure:
- Slides 1-3: Introduction (inchangé)
- Slides 4-11: A quoi ça sert? (déplacé, déjà numéroté)
- Slides 12+: Décisions + Synthesis (à renuméroter, offset +8)
"""

import re

def renumber_slides(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern pour trouver les commentaires de slides : <!-- Slide XX:
    # On va chercher tous les slides après 11 et ajouter +8

    def replace_slide_number(match):
        slide_num = int(match.group(1))
        # Si le slide est > 11, on ajoute +8
        if slide_num > 11:
            new_num = slide_num + 8
            return f"<!-- Slide {new_num}:"
        else:
            # Slides 1-11 restent inchangés
            return match.group(0)

    # Regex pour capturer "<!-- Slide XX:"
    pattern = r'<!-- Slide (\d+):'

    # Remplacer tous les numéros
    new_content = re.sub(pattern, replace_slide_number, content)

    # Écrire le résultat
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Slides renumérotées: {input_file} → {output_file}")

    # Compter les slides
    slides_count = len(re.findall(r'<!-- Slide \d+:', new_content))
    print(f"📊 Total slides: {slides_count}")

if __name__ == '__main__':
    input_file = '/home/giak/Work/MnemoLite/demonstration/2.0/index_v3.1.0.html'
    output_file = input_file  # Overwrite
    renumber_slides(input_file, output_file)
