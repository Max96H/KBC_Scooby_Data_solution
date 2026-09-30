# Pitch

## Description courte (Builderbase, environ 80 mots)

> **Moments** remplace les campagnes par une décision par client et par moment de vie. Un moteur déterministe détecte le moment (bébé, premier salaire, arnaque en cours, tension financière), choisit **une seule** action utile et le bon canal (app, voix, humain), et explique toujours pourquoi. Le même signal peut mener à des décisions opposées : proposer à Emma, accompagner Sofia sans rien vendre. Et quand rien n'est utile, Moments s'abstient. Le LLM met en forme, il ne décide jamais : auditable, conforme, et 2,3 M clients décidés en une minute.

## Pitch de 60 secondes

Aujourd'hui, une banque parle à ses clients par campagnes : un segment, un message, une date d'envoi. Le client reçoit ce que la banque veut vendre, au moment où la banque l'a décidé.

Nous inversons ça. Pour chaque client, Moments détecte le moment de vie dans lequel il se trouve, et décide **une seule** chose utile, sur le bon canal, avec une explication.

Emma et Sofia viennent toutes les deux d'avoir un bébé. Emma reçoit une proposition d'assurance famille. Sofia, dont le budget est sous tension, ne reçoit **aucune offre** : un budget prévisionnel et un conseiller. Même signal, décision opposée.

Marcel, 78 ans, est en train de se faire arnaquer : pause de dix minutes, message vocal. Thomas n'a besoin de rien : on ne le dérange pas.

Techniquement, le LLM ne décide jamais. La décision est déterministe et auditable, avec 33 000 clients par seconde sur un seul cœur. Le LLM ne fait que rédiger, et ses textes sont réutilisés par segment. C'est ce qui rend la personnalisation possible pour 2,3 millions de clients, conforme au RGPD, et pour quelques centaines de dollars par mois.

## Questions probables du jury

**« Ce n'est que des règles, où est l'IA ? »**
C'est un choix. Les règles sont les garde-fous et l'explication ; l'apprentissage (bandit, efficacité) ajuste ce qui peut l'être ; le LLM rédige. En production, `life_event` et `financial_stress` deviendraient des modèles entraînés, et les règles resteraient la couche de sécurité. On ne veut pas qu'un modèle opaque décide de vendre à quelqu'un en difficulté.

**« Comment ça passe à 2,3 M clients ? »**
Décision : mesurée, environ 70 s pour 2,3 M sur un cœur, et c'est parallélisable. Rédaction : seulement pour les clients avec une action, et mise en cache par segment. Le calculateur est dans l'espace conseiller.

**« Et la vie privée ? »**
Consentement par famille (une famille coupée n'est pas calculée), catégories art. 9 exclues avant tout calcul, LLM qui ne reçoit aucune donnée client, feedback pseudonymisé, crédit toujours validé par un humain.

**« Le client ne va-t-il pas trouver ça intrusif ? »**
C'est pour ça qu'il y a le panneau « pourquoi », la réaction « Ne plus voir ça » (définitive), le plafond d'un message proactif par semaine, les heures calmes, et l'abstention par défaut.

**« Comment évitez-vous que l'optimisation dérive vers le clickbait ? »**
On optimise l'action utile complétée (+1,0), pas le clic (+0,3). L'apprentissage pèse au maximum 30 % et ne franchit jamais un garde-fou. Un tableau d'équité alerte si une tranche d'âge reçoit plus de pression commerciale.

**« Qu'est-ce qui n'est pas fini ? »**
Données synthétiques, poids non calibrés, feedback simulé, aucune intégration avec les systèmes de KBC. C'est écrit dans le README.

**« Pourquoi KBC en particulier ? »**
Une bancassurance voit les deux côtés d'un moment de vie : l'argent et la protection. Un bébé, c'est une épargne et une assurance. Un seul moteur, un seul catalogue, tous les canaux, y compris l'assistant Kate et les conseillers en agence.
