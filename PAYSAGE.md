# Paysage : sprezzature-audio en contexte

Le tableau ci-dessous note sept outils de transcription automatique, de diarisation, d'identification de locuteurs et de traduction de sous-titres, une colonne étoilée par axe. Une note va de 1 (faible) à 5 (excellent) ; une cellule marquée `--` signifie que l'outil ne traite pas du tout cet axe, si bien que le noter n'aurait pas de sens.

| Outil | Local-first | ASR | Diarisation | ID locuteur | Traduction multilingue | pip installable |
|---|---|---|---|---|---|---|
| **sprezzature-audio** | **5** | **4** | **4** | **4** | **4** | **5** |
| whisper (CLI OpenAI) | 5 | 4 | -- | -- | -- | 5 |
| WhisperX | 5 | 4 | 4 | -- | -- | 4 |
| pyannote.audio | 5 | -- | 5 | 3 | -- | 4 |
| Speechbrain | 4 | 3 | 3 | 4 | 2 | 3 |
| NeMo (brut) | 4 | 4 | 5 | 5 | 3 | 3 |
| AssemblyAI | 1 | 5 | 5 | 4 | 4 | 5 |
| Amazon Transcribe | 1 | 5 | 5 | 3 | 3 | 4 |

Trois colonnes désignent une tâche plutôt qu'un mot familier : **ASR** (reconnaissance automatique de la parole) est la transcription automatique ; la **diarisation** consiste à repérer qui a parlé quand, sans encore savoir le nom de personne ; l'**identification de locuteur** va un cran plus loin et fait correspondre une voix à un échantillon de référence connu pour lui coller un vrai nom. « Local-first » note à quel point un outil tourne entièrement sur la machine, sans appel au cloud nécessaire pour sa fonction principale.

## Notes

**whisper (CLI OpenAI)** transcrit la parole en texte mais n'a aucune notion de qui parle : ni diarisation, ni identification.

**WhisperX** ajoute un alignement mot à mot et une diarisation empruntée à pyannote. Il n'a aucun moyen de coller un vrai nom à un locuteur depuis un échantillon de référence.

**pyannote.audio** fait référence pour la diarisation : les chercheurs y comparent leurs nouvelles méthodes. Il ne transcrit pas du tout.

**Speechbrain** couvre un large éventail de tâches audio dans une seule bibliothèque. Son interface demande davantage de réglages qu'un simple `pip install` avant d'être prête pour la production.

**NeMo (brut)** est la boîte à outils qui contient réellement les modèles Sortformer et TitaNet que `sprezzature-audio` encapsule. Appeler NeMo directement demande davantage de code ; ce paquet échange une part de la souplesse de NeMo contre des scripts prêts à l'emploi.

**AssemblyAI et Amazon Transcribe** sont des services cloud : chaque extrait est envoyé à un serveur distant, facturé à la minute audio. Pratique, mais l'enregistrement quitte la machine, ce qui les écarte dès que tout doit rester local.

## Positionnement de sprezzature-audio

Son atout distinctif est d'être une **pile locale complète** : transcription (Whisper, via vocal-helper), diarisation (Sortformer de NeMo), identification (TitaNet) et traduction par LLM (via la connexion Ollama de sprezzature-local), le tout exécutable hors ligne sur un ordinateur portable ou un serveur. Aucune étape n'exige de joindre un service cloud.
