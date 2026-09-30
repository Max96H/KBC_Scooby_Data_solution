# Sécurité

La sécurité compte pour 10 % de la note. Elle est évaluée par l'**AI Code Audit d'Aikido**, qui cherche en priorité quatre catégories : **logique métier**, **IDOR**, **authentification**, **autorisation**. Chaque contrôle ci-dessous est implémenté **et testé** (`tests/test_security.py`, `tests/test_engine.py`).

## Contrôles par catégorie Aikido

### Authentification

| Menace | Contrôle | Où | Test |
| --- | --- | --- | --- |
| Vol de mots de passe | PBKDF2-HMAC-SHA256, 200 000 itérations, sel aléatoire, comparaison à temps constant | `security.py` | – |
| Mots de passe codés en dur | Aucun : `DEMO_PASSWORD` depuis l'environnement, sinon aléatoires écrits dans `.demo_credentials` (non versionné, `chmod 600`) | `data/generate.py` | – |
| Énumération des comptes | Même message, même code et même temps de calcul (hash factice) pour un compte inexistant | `routes/auth.py` | `test_login_wrong_password_and_unknown_user_look_identical` |
| Force brute | 5 tentatives par IP et par identifiant sur 5 minutes → HTTP 429 | `security.py` | `test_login_rate_limited` |
| Token falsifié | JWT HS256, algorithme imposé (`none` refusé), expiration obligatoire, clé depuis `SECRET_KEY` (aléatoire si absente, jamais de valeur par défaut) | `security.py`, `config.py` | `test_forged_tokens_rejected` |
| Token volé après suppression du compte | Chaque requête revérifie que le compte existe et a le même rôle | `security.py` | `test_deleted_user_token_revoked` |
| CSRF | Token dans l'en-tête `Authorization`, pas de cookie | `common.js` | – |

### Autorisation

| Menace | Contrôle | Test |
| --- | --- | --- |
| Client qui appelle les endpoints conseiller | Dépendances `require_customer` / `require_advisor` sur chaque route | `test_customer_cannot_use_advisor_endpoints`, `test_advisor_has_no_customer_view` |
| Élévation de rôle via le token | Le rôle et le client du token doivent correspondre à la base | `test_token_cannot_escalate_role_or_switch_customer` |
| Conseiller qui consulte n'importe quel client | Le journal détaillé n'est accessible que si une tâche existe pour ce client (moindre privilège) | `test_advisor_journal_requires_assigned_task` |
| Journal du moteur exposé en production | `DEMO_MODE=false` le retire des réponses client | – |

### IDOR

| Menace | Contrôle | Test |
| --- | --- | --- |
| Lire ou modifier la décision d'un autre client | **Aucun endpoint client ne prend de `customer_id`** : l'identité vient du token. Chaque accès à une décision passe par `owned_decision()` qui filtre `id AND customer_id`. Une ressource d'un autre client renvoie 404 (pas 403, pour ne pas révéler qu'elle existe) | `test_idor_on_every_decision_endpoint` |
| Modifier le consentement d'un autre client | L'écriture utilise le `customer_id` du token uniquement | `test_consent_only_changes_own_data` |
| Passer un `customer_id` en paramètre | Ignoré | `test_no_endpoint_accepts_customer_id` |
| Identifiants devinables | Décisions en UUID v4 (128 bits), format validé par regex | `test_strict_input_validation` |

### Logique métier

| Menace | Contrôle | Test |
| --- | --- | --- |
| Forcer une action via un paramètre | Le client n'envoie jamais d'`action_id` : l'action est choisie par le serveur. Un bouton n'est accepté que s'il appartient à l'action de **cette** décision (catalogue fermé) | `test_cannot_trigger_cta_of_another_action` |
| Contourner la pause anti-arnaque | `hold_until` est posé et vérifié côté serveur avec l'horloge réelle ; confirmer avant → 409 | `test_scam_hold_cannot_be_bypassed` |
| Gonfler le score d'une action (« je l'ai complétée ») | `completed` n'est posé que par le serveur lors de l'exécution d'un bouton ; le client ne peut envoyer que `seen`, `clicked`, `not_now`, `never`, `intrusive` | `test_client_cannot_self_report_completed` |
| Effacer un refus | Un refus ne peut pas être remplacé par une réaction positive | `test_positive_reaction_cannot_erase_refusal` |
| Feedback sur une abstention | Refusé (409) | `test_feedback_on_abstention_refused` |
| Vendre à un client en difficulté | Garde-fou déterministe, non influençable par l'apprentissage | `test_same_signal_opposite_decision` |

## Autres contrôles

| Sujet | Contrôle |
| --- | --- |
| Injection SQL | Requêtes 100 % paramétrées, aucune concaténation |
| Validation d'entrée | Pydantic avec `extra="forbid"`, longueurs et regex bornées, `Literal` pour les énumérations |
| Taille des requêtes | 16 Ko maximum (413) |
| XSS | Front sans `innerHTML` (DOM + `textContent`) ; CSP `default-src 'self'; script-src 'self'` ; aucun script ni style en ligne |
| Sortie du LLM | Schéma JSON contraint côté Gemini, puis revalidé : pas de balise, pas d'URL, pas de gabarit autre que `{first_name}`, pas de chiffres inventés (taux, montants) ; le LLM ne produit que du texte, le serveur construit la structure. En cas d'échec : gabarit |
| Injection de prompt | Le LLM ne reçoit aucune donnée fournie par le client (ni libellé, ni texte libre) |
| En-têtes | CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, COOP, `Cache-Control: no-store` sur l'API |
| CORS | Liste d'origines explicite, pas de credentials |
| Fuite d'erreurs | Gestionnaire global : `{"detail": "Erreur interne"}`, trace uniquement dans les logs |
| Documentation API | `/docs` désactivé par défaut (`ENABLE_DOCS`) |
| Secrets | `.env`, `.demo_credentials`, `*.db` dans `.gitignore` ; `.env.example` sans valeur ; sel de pseudonymisation généré en base |
| Conteneur | Utilisateur non-root |
| CI | GitHub Actions lance les tests à chaque push, avec des permissions en lecture seule |

## Limites assumées (PoC)

- Limitation des tentatives en mémoire (mono-instance). Production : Redis ou passerelle API.
- Pas de révocation individuelle de token avant expiration (60 min). Production : liste de révocation ou tokens courts + refresh.
- `X-Forwarded-For` volontairement ignoré : derrière un proxy, configurer `--proxy-headers` avec une liste de proxys de confiance.
- Authentification par mot de passe pour la démo. Production : authentification forte de la banque.

## Procédure Aikido (à faire pendant le hackathon)

1. Créer le compte via le lien du guide : `https://app.aikido.dev/ai-pentests/discounts/hackathon-tectonic-aikido` → **Continue with GitHub**.
2. Connecter le repo **public** du hackathon.
3. Lancer l'**AI Code Audit** (baseline) **dès que le repo existe**. Faire la **capture « avant »**.
4. Pour chaque problème : corriger, ajouter un test si possible, marquer comme **résolu** dans Aikido. Consigner ci-dessous.
5. Relancer l'audit, faire la **capture « après »**.
6. Déposer les deux captures dans `docs/aikido/` et sur Builderbase.

### Journal des corrections Aikido

| # | Problème signalé | Catégorie | Correction | Commit |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |
