# sprezzature-audio

Traitement de la parole local pour la suite [sprezzature](https://harchaoui.org/warith/sprezzature/).

Ce paquet traite **ce qui a été dit, par qui, et dans quelle langue**. Il ne touche pas aux fichiers audio au niveau du signal. Pour la conversion de formats, la découpe de formes d'onde et la séparation de sources, voir [audio-helper](https://github.com/warith-harchaoui/audio-helper).

## Ce que ça fait

| Script | Résultat |
|---|---|
| `captions_from_whisper.py` | WebVTT / SRT / transcription brute via Whisper local |
| `diarize_from_nemo.py` | RTTM + liste JSON de tours de parole via NeMo Sortformer (4 locuteurs max) |
| `identify_from_titanet.py` | Identité d'un locuteur à partir d'un échantillon vocal via NeMo TitaNet |
| `caption_diarize.py` | Pipeline combiné : sous-titres + diarisation en une seule passe |
| `name_from_transcript.py` | Deviner les noms des locuteurs depuis une transcription diarisée (règles + LLM optionnel) |
| `translate_captions.py` | Traduire un fichier VTT/SRT vers une autre langue via LLM local |

Toute l'inférence lourde tourne sur la machine. Pas de cloud. Pas de clé API.

## Installation

```sh
# Base (sans aucun modèle lourd)
pip install sprezzature-audio

# Avec la transcription (Whisper via vocal-helper)
pip install "sprezzature-audio[captions]"

# Avec la diarisation et l'identification de locuteurs (NeMo -- torch requis d'abord)
pip install torch  # choisir la version CUDA / MPS / CPU adaptée à votre machine
pip install "sprezzature-audio[diarize]"

# Avec la traduction LLM (best-engine-ai-helper + ollama)
pip install "sprezzature-audio[translate]"

# Tout
pip install "sprezzature-audio[all]"
```

## Démarrage rapide

```sh
# Transcrire une vidéo en WebVTT
python scripts/captions_from_whisper.py conf.mp4

# Transcription brute (texte)
python scripts/captions_from_whisper.py podcast.mp3 --format text

# Diariser un fichier audio (qui a parlé quand)
python scripts/diarize_from_nemo.py entretien.wav

# Pipeline complet : sous-titres + étiquettes de locuteurs
python scripts/caption_diarize.py reunion.mp4

# Deviner les noms depuis la transcription diarisée
python scripts/name_from_transcript.py reunion.speakers.vtt

# Traduire des sous-titres en anglais
python scripts/translate_captions.py conf.vtt --lang en
```

## La distinction avec audio-helper

`audio-helper` travaille au **niveau du signal** : conversion de formats, découpe, rééchantillonnage, séparation de sources avec Demucs. Il ne connaît pas les mots.

`sprezzature-audio` travaille au **niveau du contenu** : il lit la parole, l'attribue à des locuteurs et la traduit. Les deux paquets se complètent. `captions_from_whisper.py` utilise `audio-helper` en interne pour extraire un WAV 16 kHz mono avant d'appeler Whisper.

## Modèles utilisés

| Tâche | Modèle | Backend |
|---|---|---|
| ASR | `large-v3-turbo` (défaut) ou tout alias GGML | vocal-helper / pywhispercpp |
| Diarisation | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Identification | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Traduction | Configuré via les variables `SPREZZATURE_LLM_*` | best-engine-ai-helper |

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Remplacer le modèle Whisper (chemin ou alias) |
| `SPREZZATURE_CACHE_DIR` | Répertoire de cache pour les poids et les transcriptions |
| `SPREZZATURE_NO_CACHE` | Désactiver le cache de transcriptions |
| `NEMO_DIAR_MODEL` | Remplacer le checkpoint NeMo |
| `SPREZZATURE_LLM_*` | Configuration du backend LLM (voir best-engine-ai-helper) |

## Licence

BSD 3 clauses. Voir [LICENSE](LICENSE).

## Auteur

Warith Harchaoui -- [harchaoui.org/warith](https://harchaoui.org/warith/)
