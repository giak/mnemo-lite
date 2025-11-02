#!/usr/bin/env python3
"""
Script pour fixer complètement la numérotation des slides.
Compte toutes les <section> et ajoute/corrige les commentaires de slides.
"""

import re

def fix_slide_numbering(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    slide_counter = 0
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Chercher les commentaires de slide existants à SUPPRIMER
        if re.match(r'^\s*<!-- Slide \d+:', line):
            # Ignorer cette ligne (on va en créer une nouvelle)
            i += 1
            continue

        # Chercher les balises <section> pour ajouter le numéro
        if '<section' in line:
            slide_counter += 1
            # Vérifier si la ligne précédente est un commentaire de section (<!-- ===== XXX ===== -->)
            if i > 0 and '<!-- =====' in new_lines[-1]:
                # Ajouter le commentaire de slide après le commentaire de section
                pass  # On l'ajoutera après

            # Regarder en arrière pour trouver le dernier commentaire non-slide
            description = ""
            for j in range(len(new_lines) - 1, max(len(new_lines) - 5, -1), -1):
                prev_line = new_lines[j].strip()
                if prev_line.startswith('<!--') and 'Slide' not in prev_line and '=====' not in prev_line:
                    # Extraire la description
                    match = re.search(r'<!--\s*(.+?)\s*-->', prev_line)
                    if match:
                        description = match.group(1)
                        # Supprimer cette ligne qu'on va remplacer
                        del new_lines[j]
                    break

            # Créer le nouveau commentaire de slide
            if description:
                slide_comment = f"            <!-- Slide {slide_counter}: {description} -->\n"
            else:
                slide_comment = f"            <!-- Slide {slide_counter} -->\n"

            new_lines.append(slide_comment)

        new_lines.append(line)
        i += 1

    # Écrire le résultat
    with open(input_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"✅ {slide_counter} slides numérotées")
    return slide_counter

if __name__ == '__main__':
    input_file = '/home/giak/Work/MnemoLite/demonstration/2.0/index_v3.1.0.html'
    total = fix_slide_numbering(input_file)
    print(f"📊 Total: {total} slides")
