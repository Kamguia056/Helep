# L3 Patterns-in-Code Document — HELEP (Final)

Ce document détaille les patterns d'architecture logicielle implémentés dans la plateforme HELEP pour garantir sa résilience, sa scalabilité et sa maintenabilité.

---

## Part A — Pre-implemented patterns

### A.1 Choreographed Saga
- **Où :** Le flux d'événements traverse `sos-service/app/main.py` (trigger) → `dispatch-service/app/main.py` (handle_sos) → `notification-service/app/main.py` (on_event).
- **Étape de compensation :** Dans `dispatch-service/app/main.py` au sein de la fonction `handle_cancel` (lignes 96-102). L'affectation du responder est libérée (`release_assignment`) et son statut repasse à "disponible".
- **Déclencheur du rollback :** L'événement `sos.cancelled` émis par le `sos-service` lorsque l'utilisateur annule son alerte.

### A.2 Pub/Sub via Apache Kafka
- **Où :** Centralisé dans `app/events.py` présent dans chaque service.
- **Sémantique du groupe de consommateurs :** Nous utilisons `enable_auto_commit=False`. En appelant `await consumer.commit()` uniquement *après* le succès du handler (`events.py:112`), nous garantissons une livraison "at-least-once". Si le pod crash avant le commit, un autre membre du groupe reprendra le message.
- **Partitionnement par clé :** L'utilisation de `key=incident_id` (`sos-service/app/main.py:95`) assure que tous les événements liés à une même urgence arrivent sur la même partition Kafka, garantissant ainsi l'ordre chronologique des messages pour cet incident précis.

### A.3 Repository
- **Où :** Dans `app/db.py` de chaque service.
- **Pourquoi :** Ce pattern isole la logique d'accès aux données (SQLite) de la logique métier des routes FastAPI. Sans cela, une modification du schéma de base de données nécessiterait de réécrire tous les handlers de routes, couplant fortement l'API au stockage.

### A.4 Strategy
- **Où :** `dispatch-service/app/matching.py`.
- **Commutation :** Via la variable d'environnement `MATCHER`.
- **Troisième stratégie ajoutée :** `RoundRobinMatcher` (lignes 50-65). Elle permet de distribuer équitablement la charge entre les intervenants sans tenir compte de la distance.

### A.5 Outbox-lite
- **Où :** `sos-service/app/main.py` dans la fonction `trigger()` (lignes 84-85).
- **Pourquoi "lite" ?** C'est une version simplifiée car l'écriture en DB et la publication Kafka sont faites séquentiellement dans le même bloc async sans transaction atomique globale. Une "vraie" Outbox utiliserait une table intermédiaire en base de données et un relayeur séparé pour garantir la publication même en cas de crash juste après l'insert.

### A.6 Circuit Breaker (Complété)
- **Où :** `events.py` classe `CircuitBreaker` (lignes 58-105).
- **Implémentation :** J'ai implémenté la machine d'état complète :
    - `CLOSED` : Fonctionnement normal.
    - `OPEN` : Blocage immédiat après 5 échecs consécutifs (`fail_threshold`).
    - `HALF_OPEN` : Tentative de reconnexion après 10 secondes (`reset_after_s`).
- **Transitions :** Un échec en `HALF_OPEN` fait repasser en `OPEN`. Un succès en `HALF_OPEN` fait repasser en `CLOSED`.

---

## Part B — Patterns ajoutés

### B.1 Sidecar (Monitoring)
- **Où :** Défini dans les manifestes Kubernetes (ex: `helm/user-service/templates/deployment.yaml`) via les annotations Prometheus.
- **Problème résolu :** Permet d'extraire les métriques de performance sans modifier le code métier du service pour pousser les données vers un collecteur externe.
- **Arbitrage :** Préféré au push direct car moins intrusif et plus standard dans l'écosystème K8s.

### B.2 Idempotent Consumer
- **Où :** `dispatch-service/app/main.py:64` avec l'appel à `assignment_for(iid)`.
- **Problème résolu :** Dans un système distribué, les messages peuvent être délivrés plusieurs fois. Ce pattern vérifie si un incident a déjà été traité avant de procéder à une nouvelle affectation, évitant ainsi les doubles déploiements.
- **Arbitrage :** Indispensable avec Kafka en mode "at-least-once" pour éviter les incohérences d'état.

---

## Part C — Anti-patterns évités

L'architecture évite explicitement le **Shared Database (Base de données partagée)**. Chaque microservice possède sa propre instance SQLite (qui devient un PVC dédié dans K8s). Cela garantit qu'un changement de schéma dans le `user-service` ne peut pas casser le `sos-service`. La communication passe exclusivement par des contrats d'événements (Kafka) ou des API (JWT), préservant l'autonomie des services.
