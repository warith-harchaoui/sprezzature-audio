# Paysage

`sprezzature-audio` est le paquet de la parole de la suite [sprezzature](https://sprezzature.ai/), un ensemble de paquets Python pour produire du contenu web de qualité publication. Il lit une seule modalité dans les deux sens : la parole enregistrée devient du texte minuté, le texte écrit devient de la parole minutée. Rien ne part vers un service distant.

## Sa place dans l'écosystème

```
suite sprezzature
├── sprezzature-audio          ← ce paquet (les sous-titres d'un côté, la narration de l'autre)
├── sprezzature-publish        (sites, balises méta, lecture suivie ; appelle celui-ci pour la voix)
├── sprezzature-accessibility  (contrôle statique du HTML, textes alternatifs)
├── sprezzature-video          (vérification des revendications d'un film, sous-titres depuis le script)
├── sprezzature-figures        (167 types de graphiques)
├── sprezzature-maps           (choroplèthe, planche de situation, champ d'accumulation)
├── sprezzature-colors         (contraste, déficience de la vision des couleurs, palettes Tailwind)
├── sprezzature-ui             (JS natif et Tailwind, audit i18n)
├── sprezzature-cli-gui        (une ligne de commande enveloppée dans une page)
├── sprezzature-ux-laws        (30 lois, 8 décidables depuis le HTML)
└── best-engine-ai-helper      (quel modèle local tient sur cette machine)
```

Ce qui vient avant : [`audio-helper`](https://github.com/warith-harchaoui/audio-helper) au niveau du signal (conversion de format, rééchantillonnage, découpe, séparation de la voix avec Demucs) et [`video-helper`](https://github.com/warith-harchaoui/video-helper) pour extraire une piste audio d'un conteneur. Pour eux, un silence et une phrase se ressemblent. Ce paquet commence une fois l'audio utilisable, et demande ce qu'il y a dedans.

Ce qui vient après : `sprezzature-publish`, qui pilote les moteurs de narration en sous-processus pour que leurs imports lourds n'entrent jamais dans son propre graphe, et qui relie le WebVTT obtenu à la page, phrase par phrase. `sprezzature-video` consomme un script de narration et l'audio mesuré pour écrire les sous-titres d'un film.

La brique sœur qui fait le travail voisin est [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper), à qui appartiennent les voix elles-mêmes : les sessions des moteurs, la chronologie des segments, l'arithmétique des pauses, les refus. Ce paquet est l'endroit mince où son format de fil rencontre l'API de cette bibliothèque, et `scripts/_speaker.py` le dit dans sa propre docstring.

## Quand la choisir

- Vous avez un enregistrement que quelqu'un attend en texte, et cet enregistrement ne peut pas sortir du bâtiment : un entretien juridique, une consultation médicale, une réunion interne. Chaque étape tourne sur la machine qui l'appelle, y compris la traduction, qui passe par un serveur Ollama local et non par un modèle hébergé.
- Il vous faut les deux sens dans une seule dépendance et une seule convention de sortie. Une transcription et une narration atterrissent toutes deux comme de l'audio à côté d'un fichier WebVTT, écrit par le même module, avec des millisecondes tronquées et jamais arrondies dans les deux cas. C'est ce qui permet à une page de surligner la phrase en train d'être lue sans une seconde passe d'alignement.
- Vous voulez savoir si les sous-titres sont lisibles. `sprezzature-audio-audit` signale la vitesse de lecture, le chevauchement des cues, la largeur de ligne, la durée et le nombre de lignes, d'après le Netflix Timed Text Style Guide, sort en 1 au moindre défaut, et n'a besoin que de la bibliothèque standard. La justesse est la seule chose que mesure presque tout ce domaine.
- Vous voulez des locuteurs nommés, pas numérotés. La diarisation vous donne `speaker 0` et `speaker 1` ; TitaNet comparé à un dossier d'extraits de référence vous donne Alice et Bob, et `name_from_transcript` lit les prénoms dans la conversation elle-même quand aucun extrait de référence n'existe.
- Vous voulez une installation qui reste petite tant que vous ne demandez pas de modèle. Le paquet de base, c'est `click` et `langdetect`, rien d'autre ; l'étage des sous-titres est sans torch ; torch n'arrive qu'avec l'étage de diarisation et avec les voix les plus lourdes. Quelle voix parle réellement n'est pas la décision de ce paquet, et jamais celle d'un appelant : `speaker-helper` route le moteur depuis la condition qu'on lui donne, et une exécution locale, gratuite et hors ligne tombe sur Chatterbox, Turbo pour l'anglais et Multilingual pour toutes les autres langues. Ce paquet passe le texte et récupère l'audio avec ses cues.

## Quand prendre autre chose

**NVIDIA NeMo**, si la justesse décide de tout et que vous avez du matériel NVIDIA. Parakeet TDT est en tête du Open ASR Leaderboard, autour de 6,05 % de taux d'erreur de mots agrégé contre 7,7 % pour Whisper large-v3-turbo, et NeMo est l'endroit où vivent réellement Sortformer et TitaNet : ce paquet enveloppe deux de ses points de contrôle et en paie le prix en souplesse. Si vous voulez un troisième point de contrôle, ou le support commercial de Riva, allez à la source.

**pyannote.audio avec la chaîne Community-1**, quand la segmentation par locuteur est la partie difficile. Elle n'a aucun plafond de nombre de locuteurs, publie ses taux d'erreur de diarisation par jeu de données sur sa fiche de modèle, et c'est elle que la recherche en diarisation prend pour référence. Le point de contrôle Sortformer utilisé ici est bâti pour quatre locuteurs simultanés au plus, ce qui est juste pour un entretien et faux pour un conseil d'administration.

**ElevenLabs**, quand vous voulez un seul fournisseur pour les deux sens et que l'enregistrement peut quitter votre machine. Scribe est en tête des comparatifs indépendants de justesse en anglais, 3 à 4 % de taux d'erreur de mots, plus de 90 langues, et une diarisation jusqu'à 32 locuteurs ; le côté synthèse est la référence à laquelle tous les autres se mesurent, et les deux moitiés rendent des minutages. Vous payez à l'heure et au caractère, et votre audio est sur le serveur de quelqu'un d'autre.

**Chatterbox ou XTTS v2 pilotés directement**, quand cloner une personne précise est le travail plutôt qu'une étape. Chatterbox clone depuis dix secondes et a battu ElevenLabs dans un test d'écoute à l'aveugle ; XTTS v2 couvre dix-sept langues depuis six secondes. Chatterbox est d'ailleurs ce vers quoi `speaker-helper` route ici pour une exécution locale hors ligne : la question n'est donc pas l'accès mais la maîtrise. Allez au moteur lui-même quand vous voulez ses variantes, ses réglages et son échantillonnage sous la main, plutôt qu'à travers un routeur dont l'objectif est la qualité d'un document lu à voix haute. Le plafond de qualité appartient au moteur dans les deux cas, pas à l'enveloppe.

**Piper**, pour un Raspberry Pi, une borne, ou tout endroit où 44 variantes de langue et de région comptent plus que le naturel. Il est plus petit que Kokoro et couvre plus de locales. À noter : le dépôt maintenu est passé à l'Open Home Foundation sous GPL-3.0-or-later, qui n'est pas la même promesse de licence que le MIT archivé.

**AssemblyAI ou Deepgram**, pour un produit de transcription plutôt qu'une étape de transcription. Un tarif horaire bien en dessous du dollar, du flux sous 150 ms, la diarisation incluse, un engagement de service, et quelqu'un à qui téléphoner. Ce paquet n'a rien de tout cela et n'essaie pas.

**Vosk**, quand la contrainte est le flux temps réel sur un appareil sans accélérateur. Sa justesse est de l'époque Kaldi, nettement en dessous de Whisper, et il tourne en temps réel sur un Raspberry Pi dans une vingtaine de langues, ce que Whisper ne fait pas.

## Les idées à prendre

Classées par ce qu'elles rapportent au regard de ce qu'elles coûtent.

**[pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) : dire quand on touche le plafond.** Leur chaîne n'a pas de nombre de locuteurs fixé et publie son taux d'erreur par jeu de données ; la nôtre est épinglée sur un point de contrôle à quatre locuteurs et n'en dit rien. Ici : `scripts/diarize_from_nemo.py` accepte déjà `--model` et `NEMO_DIAR_MODEL`, donc le point de contrôle est interchangeable ; ce qui manque, c'est un refus. Quand la liste de tours revient avec exactement quatre identifiants distincts sur un long enregistrement, Sortformer a probablement replié une cinquième voix dans une quatrième, et le script devrait le dire sur stderr et dans le JSON plutôt que de rendre une réponse assurée. Coût : une après-midi, un champ de plus, aucune dépendance nouvelle. Meilleur rapport de la liste, parce que la capacité est là et que seule l'honnêteté manque.

**[Piper](https://github.com/OHF-Voice/piper1-gpl) : nommer une voix par ce qu'elle est.** Les identifiants Piper se lisent `fr_FR-siwis-medium` : langue, région, locuteur et niveau de qualité dans une seule chaîne. Les identifiants Kokoro se lisent `af_bella`, où deux lettres encodent la langue et le genre et rien d'autre, et `scripts/pick_voice.py:68` porte un commentaire de sept lignes qui les décode pour le lecteur. Ici : `sprezzature-audio-voice` devrait imprimer le triplet décodé à côté de l'identifiant brut, pour que la liste se parcoure sans le commentaire. Coût : une heure. La correspondance est déjà écrite, en prose, dans ce commentaire.

**[Otter.ai](https://otter.ai/) : enrôler une voix une fois, pas à chaque exécution.** Otter apprend la voix d'un locuteur une fois et le nomme dans toutes les réunions suivantes. Ici, `scripts/identify_from_titanet.py` recalcule le centroïde de référence depuis les fichiers WAV de `--refs` à chaque exécution, ce qui est la moitié lente du travail pour une distribution récurrente. Un petit magasin d'enrôlement sous `~/.cache/sprezzature-skill/voices/`, indexé sur l'étiquette du modèle TitaNet, l'éviterait. Coût : une après-midi, plus une règle que cette suite a déjà apprise à ses dépens : un cache ne doit jamais changer une réponse en silence, donc le magasin a besoin d'une commande qui le liste et d'un drapeau qui l'ignore.

**[ElevenLabs `/with-timestamps`](https://elevenlabs.io/docs/overview/capabilities/speech-to-text) et [Kyutai TTS](https://huggingface.co/kyutai/tts-1.6b-en_fr) : le synthétiseur connaît déjà les minutages.** Tous deux rendent l'alignement issu de la génération elle-même plutôt que de réécouter leur propre sortie. Ce paquet reçoit de `speaker-helper` des cues au niveau du bloc, ce qui suffit pour surligner une phrase et pas pour surligner un mot. Ici : un drapeau `--word-cues` sur la commande de narration, qui écrirait un second VTT à la granularité du mot. Coût : une demi-semaine, et c'est à moitié bâti, parce que l'un des moteurs que porte `speaker-helper`, Kokoro, expose déjà les durées par jeton à l'étape de phonémisation qu'il exécute de toute façon. La part honnête, c'est que les autres ne le font pas, donc le drapeau doit refuser moteur par moteur plutôt qu'estimer, et le moteur est le choix du routeur, pas celui de l'appelant.

**[Deepgram](https://deepgram.com/learn/best-speech-to-text-apis) et [AssemblyAI](https://www.assemblyai.com/blog/top-speaker-diarization-libraries-and-apis) : la confiance mot à mot.** Tous deux rendent le degré de certitude du modèle, mot par mot, et c'est exactement ce qu'un relecteur humain veut voir surligné. `scripts/audit_captions.py` a huit règles, et toutes sont géométriques : vitesse, largeur, durée, chevauchement, nombre de lignes. Une neuvième, `cue-low-confidence`, serait la première règle qui porte sur le contenu plutôt que sur la forme. Coût : une après-midi pour faire traverser `captions_from_whisper.py` aux probabilités de jetons de pywhispercpp, et une vraie décision de conception avant cela, parce que WebVTT n'a pas de champ de confiance : une ligne `NOTE`, un JSON à côté, ou rien.

**[whisper-diarization](https://github.com/MahmoudAshraf97/whisper-diarization) : séparer la musique d'abord.** Il lance une séparation de sources avant de diariser, et la musique sous la parole est la cause habituelle d'un locuteur fantôme en trop. Ici : `--separate` sur `sprezzature-audio-diarize`, en appelant le chemin Demucs que `audio-helper` embarque déjà et que l'extra `[diarize]` déclare déjà. Coût : une journée, et cela double à peu près la durée d'exécution, donc cela reste un drapeau et ne devient jamais un défaut.

**[WhisperX](https://github.com/m-bain/whisperX) : l'alignement phonémique forcé, et pourquoi pas ici.** Sa passe d'alignement wav2vec2 tire des minutages de mots sous 100 ms, contre les 200 à 500 ms que donnent les bornes de segment de whisper.cpp. Cette précision est précisément ce que mesurent `cue-too-fast` et `cue-too-brief`, donc elle affinerait l'audit autant que les sous-titres. Refusée sur le chemin par défaut : l'extra `[captions]` est sans torch aujourd'hui et c'est une propriété qui mérite d'être gardée, et l'alignement demande un modèle par langue en plus de torch. Défendable plus tard comme un extra `[captions-align]` distinct, jamais comme un défaut.

**[Vosk](https://alphacephei.com/vosk/) et les API hébergées : le flux temps réel, et pourquoi pas ici.** Tous les concurrents hébergés et Vosk rendent des résultats partiels pendant que l'audio arrive encore. Ce paquet est fichier d'entrée, fichier de sortie, de bout en bout, et l'audit des sous-titres est défini sur une piste complète : `cue-overlap` compare un cue à celui d'avant, et un cue en flux n'a pas de voisin arrêté. Refusé exprès. C'est une autre architecture, pas un drapeau manquant.

## Comment le domaine se découpe

**Par sens.** La plupart des entrées ici ne font qu'une chose. Whisper et ses portages, pyannote, Vosk et AssemblyAI ne font que lire la parole ; Kokoro, Piper, Chatterbox, XTTS v2, F5-TTS, Kyutai et MeloTTS ne font que la produire. Les outils qui font les deux sont soit de grandes boîtes à outils de recherche (NeMo, SpeechBrain), soit des plateformes hébergées (ElevenLabs, Azure Speech, Deepgram, l'API audio d'OpenAI). Il y a très peu de chose au milieu, et le milieu est l'endroit où se tient ce paquet : assez petit pour un `pip install`, assez local pour tourner réseau coupé, et pointé dans les deux sens.

**Par où va l'audio.** La ligne de partage qui décide la plupart des adoptions réelles n'est pas la justesse, c'est de savoir si l'enregistrement quitte la machine. Une API hébergée s'adopte plus vite, coûte moins cher à l'heure qu'un GPU, et se trouve immédiatement disqualifiée dans un hôpital, un cabinet d'avocats ou chez un industriel de la défense. Les piles locales paient cela en installation, en matériel, et en heures passées à faire s'entendre NeMo et torch sur une version de CUDA. La comparaison honnête n'est pas « lequel est meilleur » mais « quelle contrainte est bloquante ».

**Par bibliothèque contre sortie finie.** pyannote rend un objet d'annotation ; NeMo rend des tenseurs et un fichier de configuration ; faster-whisper rend des segments. Transformer l'un de ces trois en un `.vtt` qu'un navigateur accepte est un travail que quelqu'un refait dans chaque projet. Les outils qui écrivent le fichier (whisper.cpp, WhisperX, whisper-diarization, les API hébergées, ce paquet) font quelque chose que les bibliothèques se refusent délibérément à faire, et c'est une contribution plus petite qu'un modèle mais réelle. Ce paquet va un cran plus loin et audite le fichier qu'il vient d'écrire, ce que rien d'autre dans la table ne fait.

**Par licence, et c'est plus embrouillé qu'il n'y paraît.** Le code et les poids sont licenciés séparément, et souvent différemment. Kokoro et NeMo sont en Apache-2.0 des deux côtés. Chatterbox est en MIT. Le code de pyannote est en MIT et les poids de Community-1 en CC-BY-4.0, derrière une barrière d'accès Hugging Face. Les poids de XTTS v2 sont sous Coqui Public Model License, qui est non commerciale. Les poids de référence de F5-TTS sont non commerciaux eux aussi. Ceux de Kyutai sont en CC-BY-4.0, ce qui est permissif et n'est pas la même promesse qu'Apache : c'est pourquoi ce paquet met Kyutai derrière son propre extra plutôt que dans l'installation par défaut.

## Comparaison

Chaque alternative est notée de 1 à 5 sur chaque critère, plus c'est mieux (⭐ faible à ⭐⭐⭐⭐⭐ le plus fort). Les notes relèvent d'un jugement raisonné, pas d'un benchmark, et chaque axe est orienté de sorte que plus d'étoiles signifie plus fort sur ce trait : pour le coût, plus d'étoiles signifie moins cher ou plus ouvert ; pour le poids d'installation, plus d'étoiles signifie plus léger. Une seule `⭐` signifie que l'outil ne tente pas du tout ce travail, ce qui, sur une échelle de capacité, vaut 1. La source lisible par machine est [`assets/paysage.csv`](assets/paysage.csv) : 23 outils sur 15 critères.

| Outil de parole | Local et hors ligne | Gratuit ou open source | Licence permissive pour un usage commercial | Qualité de la reconnaissance | Segmentation par locuteur | Identification nommée du locuteur | Synthèse vocale | Clonage de voix | Piste minutée produite | Couverture multilingue | Installation légère sans torch | Vitesse sur une machine ordinaire | Traitement en flux temps réel | Maturité et écosystème | Support commercial |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| sprezzature-audio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ |
| whisper.cpp | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| faster-whisper | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| WhisperX | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ |
| whisper-diarization | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| pyannote.audio | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| NVIDIA NeMo | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| SpeechBrain | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Vosk | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Kokoro | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Piper | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Chatterbox | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| XTTS v2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| F5-TTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| Kyutai TTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| MeloTTS | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| ElevenLabs | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Deepgram | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| AssemblyAI | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Azure Speech | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Amazon Transcribe | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenAI Audio API | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Otter.ai | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

![Carte de positionnement de sprezzature-audio face à 22 autres outils de parole, sur deux axes issus d'une analyse en composantes principales de la table ci-dessus. Le paquet occupe seul le coin supérieur droit, la place donnée par construction à la ligne de référence. Le coin opposé tient les plateformes hébergées : AssemblyAI tout en bas à gauche, avec Amazon Transcribe, Deepgram et Otter.ai à côté, et ElevenLabs tout en bas. Le haut à gauche tient les moteurs locaux légers qui ne font qu'un métier, whisper.cpp, faster-whisper, Vosk, Piper et Kokoro. Le bord droit tient les synthétiseurs qui clonent une voix, F5-TTS, Chatterbox et XTTS v2. L'axe horizontal oppose un outil de reconnaissance rapide et léger à une voix coûteuse qui clone ; l'axe vertical oppose l'ouvert et le local à l'acheté et au soutenu.](assets/paysage.svg)

La source est [`assets/paysage.csv`](assets/paysage.csv), la table en étoiles ci-dessus et rien de plus, et la carte se régénère avec :

```sh
python scripts/landscape_to_csv.py ~/sprezzature-audio/PAYSAGE.md \
  --out ~/sprezzature-audio/assets/paysage.csv
standpoint ~/sprezzature-audio/assets/paysage.csv \
  --outdir ~/sprezzature-audio/assets --stem paysage --check
```

La géométrie est une ACP sur corrélations, et elle est déterministe : la même table donne la même carte à chaque exécution, quel que soit le modèle qui a nommé les pôles. Les pôles s'appellent **Efficacité** et **Créativité** en largeur, **Accessibilité** et **Liberté** en hauteur. Ces quatre mots viennent d'un modèle local ; les charges ci-dessous sont le contrôle, et ce sont elles qu'il faut croire.

**Horizontal, Efficacité à gauche et Créativité à droite.** Le clonage de voix (+0,48) et la synthèse vocale (+0,38) tirent vers la droite ; la vitesse sur une machine ordinaire (−0,44), l'installation légère sans torch (−0,36), la qualité de la reconnaissance (−0,26), la maturité et l'écosystème (−0,24) et la piste minutée produite (−0,23) tirent vers la gauche. Ce que cet axe oppose vraiment, c'est un outil bon marché qui lit vite la parole contre un modèle coûteux qui invente une voix : F5-TTS, Chatterbox et XTTS v2 sont au bord droit, whisper.cpp, Vosk et faster-whisper au bord gauche. `sprezzature-audio` est tout à droite par construction, parce que c'est la ligne de référence et que `standpoint` ancre la référence en haut à droite.

**Vertical, Accessibilité en bas et Liberté en haut.** Gratuit ou open source (+0,43), licence permissive pour un usage commercial (+0,40) et local et hors ligne (+0,38) chargent vers le haut ; le support commercial (−0,34), le traitement en flux temps réel (−0,31), le clonage de voix (−0,29) et la synthèse vocale (−0,25) vers le bas. C'est l'axe qui décide la plupart des adoptions réelles : l'enregistrement quitte-t-il la machine, et quelqu'un vous doit-il une réponse quand cela casse. ElevenLabs est tout en bas, avec AssemblyAI, Deepgram, Amazon Transcribe et Azure Speech au-dessus ; toute la moitié ouverte tient dans la bande du haut.

**Deux axes portent 54,1 % de la table** (38,7 % et 15,4 %). Près de la moitié de ce que disent ces 15 critères n'est pas sur cette page. C'est attendu avec 15 critères sur 23 outils, et cela veut dire que la carte est une première orientation alors que la table est la preuve. Une chose que les axes ne portent pas, par exemple : `sprezzature-audio` et NeMo font tous deux le travail complet dans les deux sens, ce que presque personne d'autre ne fait ; la table le dit en deux colonnes, la projection dépense sa variance ailleurs. `standpoint` écrit aussi une interprétation en prose à côté de la figure ; elle n'est pas reprise ici, parce qu'un modèle qui relit des notes écrites par quelqu'un n'est pas un résultat, et que ce fichier est plus utile si les jugements restent visiblement les miens.

## Sources

- [Les chiffres du Open ASR Leaderboard pour Parakeet TDT et Whisper large-v3-turbo](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [La fiche de modèle de pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
- [Les modèles de diarisation de NVIDIA NeMo](https://docs.nvidia.com/nemo/speech/nightly/asr/speaker_diarization/models.html)
- [TitaNet, par Nithin Rao KOLUGURI, Taejin PARK et Boris GINSBURG, 2021](https://arxiv.org/pdf/2110.04410)
- [ElevenLabs Scribe](https://elevenlabs.io/blog/meet-scribe)
- [Les tarifs des API de reconnaissance de la parole, 2026](https://convertaudiototext.com/blog/speech-to-text-api-pricing-2026)
- [Les modèles de synthèse vocale locaux, chaque licence vérifiée](https://www.yaps.ai/blog/best-local-tts-models)
- [Kyutai tts-1.6b-en_fr, poids en CC-BY-4.0](https://huggingface.co/kyutai/tts-1.6b-en_fr)
- [Piper, désormais à l'Open Home Foundation](https://github.com/OHF-Voice/piper1-gpl)
- [whisper.cpp face à faster-whisper, mesuré](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)
