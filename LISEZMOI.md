# sprezzature-audio

Traitement local de la parole pour la suite [sprezzature](https://harchaoui.org/warith/sprezzature/).

On pointe l'outil vers un enregistrement (une réunion, un entretien, un cours) et il renvoie une transcription qui dit non seulement *ce qui* a été dit, mais *qui* l'a dit et *dans quelle langue*. Tout tourne sur la machine locale : aucun son n'en sort, aucune clé d'API n'est nécessaire. Pour découper, rééchantillonner ou nettoyer le signal audio lui-même (couper les silences, séparer une voix d'une musique de fond), c'est un autre métier, assuré par un paquet voisin, [audio-helper](https://github.com/warith-harchaoui/audio-helper) ; ce paquet-ci part d'un audio déjà exploitable et se demande ce qui y a été dit.

## Ce que ça fait

Six scripts, chacun une étape du pipeline. Quelques termes reviennent tout au long du tableau ci-dessous ; autant les poser une fois pour toutes plutôt que de les répéter à chaque ligne :

- **ASR** (reconnaissance automatique de la parole, de l'anglais *automatic speech recognition*) est le nom technique de la transcription automatique : transformer une onde sonore en mots écrits.
- **WebVTT** et **SRT** sont deux formats de fichier texte concurrents pour stocker des sous-titres : une liste de triplets `[début, fin, texte]`. WebVTT est le format standard du web (celui qu'attend une balise `<video>`) ; SRT est plus ancien mais lu par davantage de lecteurs vidéo.
- **RTTM** est un format texte issu du monde de la recherche en traitement de la parole, pour enregistrer *qui a parlé quand* : une ligne par tour de parole, avec un instant de départ, une durée et une étiquette de locuteur.
- **NeMo** est la boîte à outils libre de NVIDIA pour les modèles de parole ; **Sortformer** et **TitaNet** sont deux modèles NeMo précis utilisés ici (diarisation et empreinte vocale, expliqués plus bas).

| Script | Résultat |
|---|---|
| `captions_from_whisper.py` | WebVTT, SRT ou transcription brute, via un modèle Whisper local (par `vocal-helper`) |
| `diarize_from_nemo.py` | Un fichier RTTM plus une liste JSON de tours de parole, via le modèle Sortformer de NeMo (4 locuteurs maximum) |
| `identify_from_titanet.py` | L'identité d'un locuteur, mise en correspondance avec un échantillon vocal de référence, via le modèle TitaNet de NeMo |
| `caption_diarize.py` | Le pipeline combiné : transcription et tours de parole fusionnés en une seule passe |
| `name_from_transcript.py` | Une estimation du nom réel de chaque locuteur, lue sur la transcription diarisée (reconnaissance de motifs, avec un LLM en appoint facultatif) |
| `translate_captions.py` | Une copie traduite d'un fichier VTT/SRT, via un LLM local |

## Installation

```sh
# Base (sans dépendance d'apprentissage automatique)
pip install sprezzature-audio

# Avec la transcription (Whisper via vocal-helper)
pip install "sprezzature-audio[captions]"

# Avec la diarisation et l'identification de locuteurs (NeMo ; installer
# torch d'abord, la version adaptée dépend du matériel : CUDA, Apple
# silicon MPS ou simple CPU)
pip install torch
pip install "sprezzature-audio[diarize]"

# Avec la traduction par LLM (best-engine-ai-helper et un serveur Ollama local)
pip install "sprezzature-audio[translate]"

# Tout
pip install "sprezzature-audio[all]"
```

## Démarrage rapide

```sh
# Transcrire une vidéo en WebVTT
python scripts/captions_from_whisper.py conf.mp4

# Idem, en transcription brute
python scripts/captions_from_whisper.py podcast.mp3 --format text

# Diariser un fichier audio : qui a parlé quand
python scripts/diarize_from_nemo.py entretien.wav

# Pipeline complet : caption_diarize.py fusionne les fichiers de sous-titres
# et de diarisation déjà produits par les deux étapes ci-dessus (il ne prend
# pas de fichier média en entrée)
python scripts/captions_from_whisper.py reunion.mp4
python scripts/diarize_from_nemo.py reunion.mp4
python scripts/caption_diarize.py --captions reunion.vtt --diarization reunion.diarization.json

# Deviner les noms des locuteurs depuis la transcription diarisée
python scripts/name_from_transcript.py reunion.speakers.vtt

# Traduire des sous-titres en anglais
python scripts/translate_captions.py conf.vtt --lang en
```

## Ce qui distingue ce paquet d'audio-helper

`audio-helper` travaille au **niveau du signal** : conversion de formats, découpe d'une forme d'onde, rééchantillonnage, séparation d'une voix et d'une musique de fond avec Demucs. Il n'a aucune notion des mots ; un silence et une phrase se ressemblent à ses yeux.

`sprezzature-audio` travaille au **niveau du contenu** : il lit la parole, l'attribue à un locuteur et la traduit. Les deux paquets sont faits pour être utilisés ensemble, non comme des alternatives ; `captions_from_whisper.py` appelle d'ailleurs `audio-helper` en interne pour extraire un fichier WAV 16 kHz mono (le format attendu par Whisper) avant même de lancer le modèle de parole.

## Modèles utilisés

| Tâche | Modèle | Moteur |
|---|---|---|
| ASR (parole vers texte) | `large-v3-turbo` par défaut, ou tout autre jeu de poids Whisper au format GGML (le format compact qu'attend whisper.cpp, le moteur sous-jacent de `vocal-helper`) | vocal-helper / pywhispercpp |
| Diarisation (qui a parlé quand) | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Identification (faire correspondre une voix à un échantillon de référence) | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Traduction | Configurée via les variables d'environnement `SPREZZATURE_LLM_*` | best-engine-ai-helper |

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Remplacer le chemin ou l'alias du modèle Whisper |
| `SPREZZATURE_CACHE_DIR` | Répertoire de cache pour les poids Whisper et les transcriptions |
| `SPREZZATURE_NO_CACHE` | Toute valeur désactive le cache de transcriptions |
| `NEMO_DIAR_MODEL` | Remplacer le point de contrôle (*checkpoint*) NeMo de diarisation |
| `SPREZZATURE_LLM_*` | Configuration du moteur LLM (voir best-engine-ai-helper) |

## Licence

BSD à 3 clauses. Voir [LICENSE](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/LICENSE).

## Auteur

Warith Harchaoui : [harchaoui.org/warith](https://harchaoui.org/warith/)
