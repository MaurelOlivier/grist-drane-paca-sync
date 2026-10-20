# Synchronisation PACA : Grist de l'État → plusieurs documents Grist

Synchronisation **unidirectionnelle** des champs explicitement autorisés : ajouts, mises à jour des valeurs différentes, **aucune suppression**. La clé stable empêche les doublons lors des exécutions répétées. Si des clés sont déjà dupliquées dans une table, arrêt sans écriture.

## 1. Préparer Grist

- Document source : `fmevBcC9JVXK`, table `PACA`, sur l'organisation `/o/dranepaca`.
- Dans chaque document destinataire, **créer manuellement** une table `PACA` et ses colonnes, avec les **mêmes ID de colonnes et types compatibles** pour les champs à synchroniser. Les colonnes additionnelles (calculs, saisie locale) restent intactes.
- Choisir une clé métier **stable, unique et renseignée** dans toutes les lignes, par exemple `Code_INSEE` **uniquement si ce champ existe réellement et identifie chaque ligne sans ambiguïté**. Ne jamais utiliser le numéro de ligne Grist `id` comme clé entre documents.
- Utiliser des champs simples (Texte, Nombre, Booléen...) ; les colonnes Référence, Pièces jointes, dates personnalisées, champs calculés et listes doivent être traitées avec précaution : les identifiants internes Grist ne sont pas portables. Pour une référence, synchroniser plutôt un code métier dans une colonne Texte.
- Ne pas transformer une table de destination contenant déjà des doublons en table synchronisée avant nettoyage.

## 2. Configurer `config.json`

- `base_url` peut varier selon la configuration de l'instance. La valeur fournie correspond à l'URL source communiquée. Contrôler que les documents de destination appartiennent à l'organisation accessible via ce chemin ; si leur organisation diffère, adapter le code pour une URL par destination avant activation.
- Remplacer `Code_INSEE`, `Nom`, `Departement`, `Academie` par les **identifiants exacts** des colonnes de `PACA` (notamment via les options de colonne), pas nécessairement les libellés affichés.
- Mettre les IDs réels des documents destinataires dans `destinations`. L'ID est la partie de l'URL du document après `/doc/`, ou l'identifiant dans l'URL API.
- Passer `enabled` à `true` seulement après avoir créé les tables et validé la clé.
- Les colonnes non citées dans `sync_columns` ne sont jamais modifiées.
- Les fichiers de configuration ne doivent contenir **aucune clé API**.

## 3. Créer le dépôt GitHub

1. Créer un dépôt **privé** dans un espace GitHub autorisé par la politique institutionnelle.
2. Y déposer le contenu de ce dossier en conservant `.github/workflows/synchronisation.yml`.
3. Dans GitHub : `Settings > Secrets and variables > Actions > New repository secret` ; nom : **GRIST_API_KEY**.
4. Dans Grist de l'État, créer la clé API d'un compte de service si l'organisation le permet, avec les droits minimum nécessaires : lecture source et écriture sur les destinations. **La clé API hérite des droits du compte** ; elle n'a pas en elle-même un périmètre de tables fin.
5. Pour éviter un accès excessif, préférer un compte dédié n'ayant accès qu'aux documents concernés. Ne pas publier de données réelles dans les logs.

## 4. Déclenchement et validation

- Sur GitHub : `Actions > Synchronisation référentiel PACA > Run workflow`. Laisser **appliquer = false** pour une première simulation.
- Lire les résultats : nombre d'ajouts et de mises à jour par destination.
- Après vérification, relancer avec **appliquer = true**.
- Ensuite, le workflow est programmé le lundi à 05:17 **UTC** (07:17 en été / 06:17 en hiver en France métropolitaine), horaire indicatif : GitHub peut différer ou omettre certaines exécutions.
- Une exécution répétée ne recrée pas les lignes déjà identifiées par la clé ; elle ne modifie que les champs différents.
- Une erreur HTTP peut provoquer une synchronisation partielle ; relancer après correction pour reprendre. Le processus est convergent, mais il n'est pas transactionnel entre documents.

## 5. Sécurité, limites et contrôle

- Le CSV public seul n'est **pas** utilisé : l'API lit les documents avec authentification (secret GitHub Actions). Si l'instance Grist de l'État bloque GitHub Actions, une exécution depuis un environnement institutionnel autorisé sera nécessaire.
- Le script ne supprime jamais de lignes : si une entrée disparaît du référentiel source, elle restera dans les destinations. On peut ajouter plus tard une colonne `Actif` et la synchroniser, ou concevoir une procédure d'archivage contrôlée.
- Il détecte les doublons dans les deux tables avant toute écriture et n'écrase pas les colonnes locales.
- Si une destination présente une erreur d'accès ou de schéma pendant une écriture, les documents précédemment traités peuvent être déjà modifiés.
- N'utilisez GitHub Actions pour des données RH/personnelles qu'après vérification des règles de votre organisation ; pour un référentiel géographique public, le risque est généralement moindre, mais la clé conserve des privilèges importants.
- `max_changes_per_destination` protège d'une mise à jour accidentelle trop large. Fixer ce seuil selon la taille réelle.

## 6. Tests hors production

Lancer `python -m unittest discover -s tests -v`, puis `GRIST_API_KEY=... python sync.py` pour une simulation locale (ne jamais mettre la clé dans l'historique du shell ni dans un fichier versionné). Enfin `python sync.py --apply` après validation.

Documentation de référence : https://support.getgrist.com/api/ et https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
