# sprezzature-audio

Traitement local de la parole pour la suite [sprezzature](https://sprezzature.ai/).

On pointe l'outil vers un enregistrement (une réunion, un entretien, un cours) et il renvoie une transcription qui dit non seulement *ce qui* a été dit, mais *qui* l'a dit et *dans quelle langue*. Il travaille aussi dans l'autre sens : une page de texte devient une narration avec sa piste minutée. Tout tourne sur la machine locale : aucun son n'en sort, aucune clé d'API n'est nécessaire. Pour découper, rééchantillonner ou nettoyer le signal audio lui-même (couper les silences, séparer une voix d'une musique de fond), c'est un autre métier, assuré par un paquet voisin, [audio-helper](https://github.com/warith-harchaoui/audio-helper) ; ce paquet-ci part d'un audio déjà exploitable et se demande ce qui y a été dit.

## Comment ça marche

![Schéma de flux. En haut, un enregistrement ou une page de texte alimente deux voies. La voie de gauche transforme le son en texte : elle transcrit avec un Whisper local, dit qui a parlé quand avec NeMo Sortformer, nomme les locuteurs à partir d'une voix de référence, et traduit, puis rend du WebVTT, du SRT ou une transcription simple. La voie de droite transforme le texte en son : elle détecte la langue, choisit la voix qui la parle, mesure chaque fichier audio et découpe les repères, puis rend un WAV et son WebVTT. Les deux se rejoignent en un seul résultat, le même contrôle de la piste de repères quel que soit le sens qui l'a écrite.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-audio/main/assets/comment-ca-marche.svg)

## Ce que ça fait

Quinze outils. Chacun est sa propre commande, et chacun est aussi une sous-commande de la porte d'entrée `sprezzature-audio` (alias `make-audio`). Quelques termes reviennent dans les tableaux ci-dessous ; les voici une fois pour toutes :

- **ASR** (reconnaissance automatique de la parole, de l'anglais *automatic speech recognition*) est le nom technique de la transcription automatique : transformer une onde sonore en mots écrits.
- **WebVTT** et **SRT** sont deux formats de fichier texte pour les sous-titres : une liste de triplets `[début, fin, texte]`. WebVTT est le standard du web (celui qu'attend une balise `<video>`) ; SRT est plus ancien et lu par davantage de lecteurs vidéo.
- **RTTM** (*Rich Transcription Time Marked*) est un format texte issu de la recherche en traitement de la parole, pour noter *qui a parlé quand* : une ligne par tour de parole, avec un instant de départ, une durée et une étiquette de locuteur.
- La **diarisation** est l'étape qui marque qui a parlé quand, sans connaître le nom de personne.
- **NeMo** est la boîte à outils libre de NVIDIA pour les modèles de parole ; **Sortformer** (diarisation) et **TitaNet** (empreinte vocale) sont deux modèles NeMo utilisés ici.
- **WER** (taux d'erreur de mots), **DER** (taux d'erreur de diarisation) et **RTF** (facteur temps réel : durée de calcul divisée par la durée de l'audio) sont les trois mesures que rend `benchmark`.

### De la parole au texte

| Commande | Porte d'entrée | Résultat |
|---|---|---|
| `sprezzature-audio-captions` | `captions` | WebVTT, SRT ou transcription brute d'un fichier audio ou vidéo, par un modèle Whisper local (`vocal-helper`, au-dessus de whisper.cpp). Orientation du vocabulaire avec `--prompt`, `--vocab`, `--vocab-from`, `--auto-project`. |
| `sprezzature-audio-diarize` | `diarize` | Un fichier RTTM et une liste de tours `.diarization.json`, par NeMo Sortformer (un point de contrôle conçu pour 4 locuteurs au plus). |
| `sprezzature-audio-identify` | `identify` | Un `.speakers.json` qui associe chaque locuteur diarisé à un nom, en comparant des empreintes TitaNet à un dossier de WAV de référence (`--refs`, un fichier par locuteur connu). |
| `sprezzature-audio-pipeline` | `pipeline` | Un WebVTT, un SRT ou un texte étiqueté par locuteur, fusionné à partir d'un fichier de sous-titres et d'un `.diarization.json` déjà sur le disque (et, en option, d'un `.speakers.json`). Il ne prend aucun fichier média. |
| `sprezzature-audio-name` | `name` | Un `speakers.json` deviné depuis la transcription elle-même : motifs de présentation et d'interpellation, plus une passe par un modèle local quand `--ollama` est donné. |
| `sprezzature-audio-translate` | `translate` | Un `.vtt` traduit (`<stem>.<lang>.vtt`) et un extrait `<video>` à deux pistes sur la sortie standard, par un modèle local. La langue cible est `--lang`, ou détectée depuis la page qui entoure le média (`--in`, `--context`). |

### Contrôler le résultat

| Commande | Porte d'entrée | Résultat |
|---|---|---|
| `sprezzature-audio-audit` | `audit` | Chaque repère qui ne peut pas être lu au rythme où il passe : inversé, chevauchant, vide, trop bref, trop long, trop rapide, trop large, trop de lignes. Les valeurs par défaut suivent le Netflix Timed Text Style Guide ; chaque seuil est une option. Code de sortie 1 au moindre constat. Aucun modèle, aucun réseau. |
| `sprezzature-audio-benchmark` | `benchmark` | Le WER entre deux transcriptions, le DER entre deux fichiers RTTM, et le RTF d'une commande chronométrée (`--time-command`). |

### Du texte à la parole

Une narration arrive sous forme d'un fichier audio et d'un WebVTT, la même convention qu'une transcription, pour qu'une page suive la lecture phrase par phrase.

| Commande | Porte d'entrée | Résultat |
|---|---|---|
| `sprezzature-audio-narrate-kokoro` | `narrate` | `narration.wav` (ou `--audio-format mp3`) et `narration.vtt` dans `--out-dir`, à partir d'un fichier JSON `--segments`, avec la voix Kokoro : 54 voix intégrées en huit langues, l'anglais en voix américaines et britanniques. `narrate` est le nom le plus ancien, pas un moteur par défaut : le moteur qui lit un document, c'est `speaker-helper` qui le choisit (voir plus bas). |
| `sprezzature-audio-narrate-openvoice` | `narrate-openvoice` | La même chose avec OpenVoice, qui sait cloner une voix à partir d'un court échantillon (`--voice-sample`). |
| `sprezzature-audio-narrate-chatterbox` | `narrate-chatterbox` | La même chose avec Chatterbox. |
| `sprezzature-audio-voice` | `voice` | Les voix intégrées de chaque moteur ; `--sample` écrit un court extrait de démonstration par voix, et `--measure` les classe selon l'amplitude de leur hauteur. |

Les trois commandes de narration partagent les mêmes options, parce que `sprezzature-publish` les pilote indifféremment. Elles impriment un rapport JSON d'une ligne sur la sortie standard : chemin de l'audio, durée, chemin des repères, voix et langue, plus la langue détectée, le recours éventuel à une langue de repli, et les indications de voix que le moteur a ignorées.

Ce paquet ne choisit pas le moteur de voix, et son appelant non plus. Cette décision appartient au routeur de [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper), à qui appartiennent les moteurs. `sprezzature-publish` interroge le routeur puis lance l'enveloppe correspondante ici. Sans `--voice`, la langue est détectée dans le texte et une voix qui la parle est choisie. C'est important : la langue détectée est ce sur quoi travaille le phonémiseur, si bien qu'un texte français lu comme de l'anglais n'est pas du français avec un accent, ce sont les règles d'orthographe anglaises appliquées à des mots français.

### Préparer une machine

| Commande | Porte d'entrée | Ce qu'elle fait |
|---|---|---|
| `sprezzature-audio-install` | `install` | Télécharge à l'avance un modèle Whisper GGML (`--model`, `large-v3-turbo` par défaut) pour que la transcription tourne hors ligne. |
| `sprezzature-audio-install-diarize` | `install-diarize` | Vérifie que NeMo s'importe, ne lance `pip install nemo_toolkit[asr]` que s'il ne s'importe pas (`--no-install` saute cette étape), et télécharge à l'avance les points de contrôle Sortformer et TitaNet (`--only` pour un seul des deux). |
| `sprezzature-audio-install-voice` | `install-voice` | Télécharge les poids d'un moteur de narration (`--engine kokoro`, `openvoice`, `chatterbox` ou `all`, la valeur par défaut) et vérifie la présence d'un espeak-ng système. |

Deux autres commandes ne sont pas des outils : `sprezzature-audio tools` liste les quinze et dit lesquels s'importent sur cette machine, et `sprezzature-audio-mcp` sert la surface MCP (voir plus bas).

## Installation

Une ligne. Sous-titres, diarisation, identification des locuteurs, traduction, narration et surfaces HTTP et MCP s'installent avec elle.

```sh
pip install sprezzature-audio
```

Il n'y a pas d'extra de fonctionnalité. La suite les a versés dans l'installation de base le 2026-11-01. Il reste un extra, et ce n'est pas une fonctionnalité : `[dev]` est l'outillage de test (pytest, ruff).

Ce que pip ne peut pas faire à votre place :

```sh
# Programmes système. ffmpeg lit les fichiers médias ; Kokoro phonémise par espeak-ng.
brew install ffmpeg espeak-ng          # ou : apt install ffmpeg espeak-ng

# Les poids se téléchargent à la demande, ils ne sont pas dans la roue.
sprezzature-audio-install                             # Whisper large-v3-turbo
sprezzature-audio-install-diarize --no-install        # Sortformer et TitaNet
sprezzature-audio-install-voice --engine kokoro       # deux fichiers, environ 354 Mo
sprezzature-audio-install-voice --engine chatterbox   # environ 1 Go, depuis Hugging Face
```

OpenVoice demande une étape de plus. Son paquet Python est publié sur GitHub sans roue, et une roue publiée ne peut pas dépendre d'une URL git ; donc, depuis un clone :

```sh
pip install -r scripts/requirements-narrate-openvoice.txt
sprezzature-audio-install-voice --engine openvoice
```

Deux conséquences à énoncer plutôt qu'à découvrir :

- **Python 3.10 à 3.13.** `requires-python` vaut `>=3.10,<3.14`, parce que `vocal-helper`, `audio-helper`, `video-helper` et `speaker-helper` déclarent tous `<3.14` aux versions que nomme le manifeste.
- **torch vient avec**, par `speaker-helper[chatterbox]` et `nemo_toolkit[asr]`. Importer la bibliothèque ne le charge pas : `import sprezzature_audio` pour lire un WebVTT ne touche aucun modèle, et un test l'impose.

## Démarrage rapide

La porte d'entrée liste chaque outil. Un script doit appeler la commande propre de l'outil.

```sh
sprezzature-audio --help                 # le catalogue, une ligne par outil
make-audio --help                        # la même commande, sous son ancien nom
sprezzature-audio tools                  # quels outils s'importent sur cette machine
sprezzature-audio captions --help        # les options d'un outil, par la porte d'entrée
sprezzature-audio-captions --help        # les mêmes options, par la commande de l'outil
```

Les deux noms mènent au même groupe click, ils ne peuvent donc pas diverger. Tout argument placé après le nom de l'outil va à cet outil, `--help` compris : la porte d'entrée ne répond à `--help` qu'avant le nom d'un outil.

```sh
# Transcrire une vidéo en WebVTT (écrit conf.vtt)
sprezzature-audio-captions conf.mp4

# Idem, en transcription brute (écrit podcast.txt)
sprezzature-audio-captions podcast.mp3 --format text

# Qui a parlé quand (écrit entretien.rttm et entretien.diarization.json)
sprezzature-audio-diarize entretien.wav

# Qui a dit quoi : le pipeline fusionne les deux fichiers écrits par les étapes ci-dessus
sprezzature-audio-captions reunion.mp4
sprezzature-audio-diarize reunion.mp4
sprezzature-audio-pipeline --captions reunion.vtt --diarization reunion.diarization.json
# écrit reunion.speakers.vtt

# Deviner les noms des locuteurs depuis la transcription attribuée
sprezzature-audio-name reunion.speakers.vtt --out reunion.speakers.json

# Traduire des sous-titres en anglais (écrit conf.en.vtt)
sprezzature-audio-translate conf.vtt --lang en

# Vérifier que les sous-titres se lisent au rythme où ils passent
sprezzature-audio-audit conf.vtt

# Narrer une liste de blocs (écrit out/narration.wav et out/narration.vtt)
echo '[{"text": "Premier paragraphe."}, {"text": "Deuxième paragraphe."}]' > segments.json
sprezzature-audio-narrate-kokoro --segments segments.json --out-dir out
```

D'autres appels, chacun avec les fichiers qu'il écrit, sont dans [EXAMPLES.md](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/EXAMPLES.md).

## En bibliothèque

`import sprezzature_audio` rend le moteur, pas seulement une chaîne de version. Ce qui s'importe tout de suite, c'est tout ce qui n'a besoin d'aucun modèle : le lecteur et l'écrivain WebVTT, le contrôle des sous-titres, l'attribution des locuteurs sur une transcription existante, le WER et le DER, la sonde de l'accélérateur et la détection de langue. C'est l'ensemble que sert l'API HTTP, pour la même raison : c'est rapide et c'est pur.

```python
import sprezzature_audio as audio

cues = audio.parse(open("talk.vtt").read())
for constat in audio.audit_cues(cues):      # trop rapide, trop court, trop large
    print(constat)

print(audio.write_srt(cues))                # VTT -> SRT, le même lecteur
ref = audio.normalise_words(texte_reference)
hyp = audio.normalise_words(texte_hypothese)
print(audio.word_error_rate(ref, hyp)["wer"])
print(audio.describe_device())              # quel accélérateur cette machine utilise
```

La moitié adossée aux modèles se résout au premier usage (PEP 562), donc l'import ci-dessus ne coûte rien, même avec Whisper, NeMo et Kokoro installés :

```python
from pathlib import Path

audio.transcribe(Path("talk.mp4"), fmt="vtt")      # Whisper, par vocal-helper
audio.diarize(Path("talk.mp4"))                    # NeMo Sortformer

rows = audio.parse_caption_cues(open("talk.vtt").read())
translate = audio.make_ollama_translator(
    url="http://localhost:11434", model="qwen3-vl:8b", source_lang="en", target_lang="fr"
)
audio.translate_cues(rows, translate_batch=translate)

audio.narrate("kokoro", [{"text": "Bonjour."}], voice="", voice_sample=None, out_dir=Path("out"))
```

`audio.narrate` est l'adaptateur qu'emploient les commandes de narration ; le moteur de voix lui-même appartient à `speaker-helper`, et il n'est pas réexporté ici. Si un nom paresseux échoue à l'import, l'erreur dit que l'installation est cassée (tout est dans la base) et enchaîne l'erreur d'import qui nomme ce qui manque.

## API HTTP et MCP

L'application FastAPI (cadriciel web Python) sert la moitié rapide et sans modèle. Transcription, diarisation et narration en sont absentes exprès : elles chargent de gros modèles et tournent pendant des minutes, ce qui, derrière une requête synchrone, revient à un délai dépassé.

| Route | `operation_id` | Ce qu'elle fait |
|---|---|---|
| `GET /health` | `health` | Sonde de vie. |
| `GET /v1/device` | `get_device` | Quel accélérateur cette machine utilisera, sondé plutôt que lu dans une configuration. |
| `POST /v1/captions/convert` | `convert_captions` | VTT, SRT et texte brut, de l'un à l'autre. |
| `POST /v1/captions/merge` | `merge_speakers` | Sous-titres et tours de parole réunis en une piste étiquetée par locuteur. |
| `POST /v1/metrics/wer` | `measure_wer` | Le WER entre une transcription de référence et une hypothèse. |
| `POST /v1/metrics/der` | `measure_der` | Le DER entre deux ensembles de segments de locuteurs, avec la meilleure permutation d'étiquettes. |

```sh
uvicorn sprezzature_audio.api:app --host 127.0.0.1 --port 8000   # HTTP seul ; docs sur /docs
sprezzature-audio-mcp                                             # routes HTTP plus MCP sur /mcp
```

MCP (*Model Context Protocol*) est la façon dont un hôte d'agent appelle des outils. `sprezzature-audio-mcp` enveloppe la même application avec `fastapi-mcp` et monte le point d'accès sur `/mcp` ; l'`operation_id` de chaque route est le nom de l'outil MCP, donc les six outils sont les six lignes ci-dessus. Il écoute sur `127.0.0.1:8000` par défaut ; `--host`, `--port`, `SPREZZATURE_AUDIO_HOST` et `SPREZZATURE_AUDIO_PORT` le changent.

### Docker

```sh
docker compose up -d                       # l'API sur localhost:8000
curl -s localhost:8000/health
docker compose run --rm api sprezzature-audio-captions /work/talk.mp4
docker compose --profile translate up -d   # ajoute un serveur Ollama pour translate et name
```

L'image installe le paquet avec `ffmpeg` et `espeak-ng`, et sa commande par défaut est `sprezzature-audio-mcp --host 0.0.0.0 --port 8000` : un seul processus, sur un seul port, sert les routes HTTP et le point d'accès MCP sur `/mcp`. Les fichiers passent par `./work`, monté sur `/work` ; les caches de Whisper et de NeMo vont dans le volume nommé `audio-cache`, par `SPREZZATURE_CACHE_DIR`, et les poids de narration, qui ne suivent pas cette variable, dans un second, `voice-cache`, monté sur le `~/.cache` du conteneur. Les deux survivent à `docker compose down` ; `down -v` les efface. `OLLAMA_URL` pointe vers le service `ollama`. Les outils longs tournent comme des commandes dans la même image.

## Skill d'agent

La cinquième surface est le skill `sprezzature-audio` pour Claude Code et OpenCode, tenu dans le dépôt pivot [sprezzature](https://github.com/warith-harchaoui/sprezzature). [TRIGGERS.md](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/TRIGGERS.md) est la table de routage que lit un agent : quelle demande va à quel outil, sur quelle surface.

## Ce qui distingue ce paquet d'audio-helper

`audio-helper` travaille au **niveau du signal** : conversion de formats, découpe d'une forme d'onde, rééchantillonnage, séparation d'une voix et d'une musique de fond avec Demucs. Il n'a aucune notion des mots ; un silence et une phrase se ressemblent à ses yeux.

`sprezzature-audio` travaille au **niveau du contenu** : il lit la parole, l'attribue à un locuteur, la traduit, et lit un texte à voix haute. Les deux paquets sont faits pour être utilisés ensemble. `captions_from_whisper.py` extrait un fichier WAV 16 kHz mono (le format qu'attend Whisper) avant de lancer le modèle de parole, par `video-helper` d'abord, puis `audio-helper`, puis un simple appel à `ffmpeg` si aucun des deux ne s'importe.

## Modèles utilisés

| Tâche | Modèle | Moteur |
|---|---|---|
| ASR (parole vers texte) | `large-v3-turbo` par défaut, ou tout autre jeu de poids Whisper au format GGML (le format compact qu'attend whisper.cpp) | vocal-helper / whisper.cpp |
| Diarisation (qui a parlé quand) | `nvidia/diar_sortformer_4spk-v1` | NeMo |
| Identification (faire correspondre une voix à un échantillon de référence) | `nvidia/speakerverification_en_titanet_large` | NeMo |
| Traduction et devinette des noms | `qwen3-vl:8b`, par le serveur Ollama de `--url` | best-engine-ai-helper |
| Narration | Kokoro, OpenVoice, Chatterbox, choisi à chaque lecture par le routeur | speaker-helper |

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `SPREZZATURE_WHISPER_MODEL` | Remplacer le chemin ou l'alias du modèle Whisper |
| `SPREZZATURE_CACHE_DIR` | Racine du cache des poids Whisper, des points de contrôle NeMo et des résultats (`~/.cache/sprezzature-skill` par défaut). Les poids de narration l'ignorent : Kokoro et OpenVoice vont sous `~/.cache/sprezzature-skill`, Chatterbox sous `~/.cache/huggingface` |
| `SPREZZATURE_NO_CACHE` | Toute valeur désactive le cache des résultats de transcription et de diarisation |
| `OLLAMA_URL` | Valeur par défaut du `--url` de `translate` et `name`, le serveur Ollama qu'ils vérifient puis appellent (`http://localhost:11434` par défaut) |
| `SPREZZATURE_LLM_TIMEOUT` | Délai maximal, en secondes, de chaque appel au LLM (grand modèle de langage) que best-engine-ai-helper fait pour `translate` et `name` (120 par défaut). Le moteur et le serveur ne sont pas lus dans l'environnement : ces deux outils désignent eux-mêmes Ollama sur `--url` |
| `SPREZZATURE_AUDIO_HOST`, `SPREZZATURE_AUDIO_PORT` | Adresse d'écoute par défaut de `sprezzature-audio-mcp` |

## Licence

BSD à 3 clauses. Voir [LICENSE](https://github.com/warith-harchaoui/sprezzature-audio/blob/main/LICENSE).

## Auteur

Warith HARCHAOUI : [deraison.ai](https://deraison.ai/)
