# Paysage -- sprezzature-audio en contexte

Le tableau compare les outils de transcription automatique, diarisation, identification de locuteurs et traduction de sous-titres. Les étoiles vont de 1 (faible) à 5 (excellent). Les cellules vides indiquent que l'outil ne traite pas cet axe.

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

## Notes

**whisper (CLI OpenAI)** transcrit mais ne sait pas qui a parlé. Pas de diarisation, pas d'identification.

**WhisperX** ajoute l'alignement mot à mot et une diarisation via pyannote. Pas d'identification depuis un échantillon de référence.

**pyannote.audio** fait référence pour la diarisation. Il ne transcrit pas.

**Speechbrain** couvre de nombreuses tâches audio. L'installation pour la production est plus complexe.

**NeMo (brut)** fournit les modèles Sortformer et TitaNet encapsulés par `sprezzature-audio`. L'utilisation directe de NeMo demande davantage de code.

**AssemblyAI / Amazon Transcribe** sont des services cloud. Les données quittent la machine. Tarification à la minute audio.

## Positionnement de sprezzature-audio

L'avantage est la **pile complète locale** : transcription (Whisper via vocal-helper), diarisation (NeMo Sortformer), identification (TitaNet) et traduction par LLM local (sprezzature-local avec ollama). Aucun cloud requis à aucune étape.
