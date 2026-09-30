# Script de la vidéo (moins de 3 minutes)

**Préparation :** `DEMO_PASSWORD=... python -m data.generate && python -m scripts.simulate_feedback`, serveur lancé, navigateur à 1440 px, zoom 100 %. Enregistrer écran + micro. Garder un onglet ouvert sur l'espace conseiller.

**Astuce :** régénérer la base juste avant l'enregistrement (la pause de Marcel dure 10 minutes réelles).

| Temps | Écran | Voix off |
| --- | --- | --- |
| **0:00 – 0:20** | Page d'accueil, titre « Moments » | « Aujourd'hui, une banque parle à ses clients par campagnes. Nous proposons autre chose : pour chacun des 2,3 millions de clients de KBC, détecter le moment de vie, décider une seule action utile, et parfois décider de ne rien faire. » |
| **0:20 – 0:45** | Connexion **Emma** → bloc « Un nouveau membre dans la famille ? » → coulisses : signal bébé 0,95, score | « Emma achète des articles pour bébé et a commencé une simulation d'assurance famille. Le moteur détecte le moment avec une confiance de 0,95 et lui propose une seule chose : revoir sa couverture. Dans les coulisses, chaque étape est visible. » |
| **0:45 – 1:15** | Connexion **Sofia** → bloc « Un budget qui suit votre nouvelle vie » → coulisses : assurance **bloquée**, « stress ≥ 2 : aucune vente » | « Sofia vit exactement le même moment. Mais son solde baisse depuis trois mois, son épargne est à zéro, elle a des frais de retard. Même signal, décision opposée : aucune offre, un budget prévisionnel et un conseiller. C'est une règle, pas un poids : l'apprentissage ne peut pas la contourner. » |
| **1:15 – 1:40** | Connexion **Marcel** → virement bloqué, compte à rebours → clic « Je connais ce bénéficiaire » → message « Pause de sécurité en cours » → « Écouter le message » | « Marcel, 78 ans, envoie 4 900 euros à un bénéficiaire inconnu. Pause de dix minutes, message vocal, et la pause est vérifiée côté serveur : impossible de la contourner. » |
| **1:40 – 1:55** | Connexion **Thomas** → « Aucune proposition aujourd'hui » | « Et la plupart du temps ? Rien. Thomas n'a besoin de rien, alors on ne le dérange pas, et on le lui dit. » |
| **1:55 – 2:10** | Retour **Emma** → « Pourquoi je vois ça ? » → onglet **Mes données** → couper « Mon usage de l'app » → coulisses : la simulation disparaît | « Chaque message dit pourquoi il existe. Le client coupe une famille de données, et elle n'est plus calculée du tout. Santé et convictions sont exclues avant tout calcul. » |
| **2:10 – 2:40** | Espace **conseiller** : file d'attente (Sofia), efficacité, bandit, équité, calculateur de coût | « Le moteur propose, le conseiller décide. Chaque réaction nourrit l'apprentissage, qui optimise la valeur, pas le clic, et ne pèse jamais plus de 30 %. Côté coût : la décision est déterministe, 33 000 clients par seconde sur un seul cœur. Le LLM ne rédige que pour les clients avec une action, et ses textes sont réutilisés par segment : quelques centaines de dollars par mois pour 2,3 millions de clients. » |
| **2:40 – 2:55** | README, tests verts, capture Aikido | « Le LLM met en forme, il ne décide jamais. 46 tests couvrent le moteur et la sécurité, audités par Aikido. Moments : le bon geste, au bon moment, et le courage de ne rien faire. » |

**Vérifier avant d'envoyer :** durée inférieure à 3:00, son audible, aucune clé API ni mot de passe visible à l'écran.
