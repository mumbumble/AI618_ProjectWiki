"""The five model stages of the pipeline, one file each. See README.md in this folder.

encoder.py        1 encoding          bge-m3
clustering.py     2 clustering        baseline · pref                      (experimental slot)
structure.py      3 structure         candidates · reranker · Claude judgment
preference.py     4 preference        baseline · drift · align             (experimental slot)
visualization.py  5 visualization     view.html · Obsidian vault
"""
