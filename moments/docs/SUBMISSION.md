# Check-list de soumission

## Pendant le hackathon

- [ ] Repo GitHub **public** créé, projet poussé (`git init && git add . && git commit -m "Moments PoC" && git push`)
- [ ] Vérifier qu'aucun secret n'est versionné : `git ls-files | grep -E "\.env$|demo_credentials|\.db$"` ne doit rien afficher
- [ ] Aikido : compte créé, repo connecté, **audit baseline lancé**, capture « avant » dans `docs/aikido/before.png`
- [ ] Corrections Aikido consignées dans [SECURITY.md](SECURITY.md#journal-des-corrections-aikido), relance, capture « après » dans `docs/aikido/after.png`
- [ ] `pytest` au vert
- [ ] (Option) `GEMINI_API_KEY` testée en local, pas commitée
- [ ] (Option) `ELEVENLABS_API_KEY` testée en local, pas commitée
- [ ] (Option) Déploiement Cloud Run, URL testée en navigation privée

## Vidéo

- [ ] Suivre [DEMO_SCRIPT.md](DEMO_SCRIPT.md), durée **< 3 minutes**
- [ ] Aucune clé ni mot de passe visible à l'écran
- [ ] Lien accessible sans connexion (YouTube non répertorié, Loom public…)

## Builderbase (une seule personne de l'équipe)

- [ ] Description courte : [PITCH.md](PITCH.md#description-courte-builderbase-environ-80-mots)
- [ ] Lien de la vidéo
- [ ] Lien du repo GitHub
- [ ] Captures Aikido avant et après
- [ ] Ouvrir **tous les liens en navigation privée** avant de soumettre
- [ ] Soumettre. Après la soumission finale, plus aucune modification du code.

## Répartition suggérée (4 personnes)

| Rôle | Responsabilités |
| --- | --- |
| Données et moteur | `data/`, `app/engine/`, tests du moteur |
| API et sécurité | `app/routes/`, `app/security.py`, Aikido, tests de sécurité |
| Front et démo | `static/`, parcours des personas, captures |
| Pitch et vidéo | [VISION.md](VISION.md), [PITCH.md](PITCH.md), vidéo, Builderbase |
