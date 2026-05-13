# L4 Design Process Document — HELEP (Final)

## 1. Project Specification

HELEP est une plateforme critique d'intervention d'urgence conçue pour le contexte camerounais, permettant aux citoyens de déclencher des alertes SOS (en ligne ou hors-ligne) et de recevoir une assistance immédiate. La valeur métier réside dans l'automatisation de la mise en relation entre victimes et secouristes (Police, SAMU), réduisant ainsi drastiquement les délais d'intervention. Les utilisateurs principaux sont les citoyens (victimes), les responders (intervenants), la police (supervision) et les administrateurs système.

## 2. Requirements Analysis

### 2.1 Functional requirements

| # | Requirement | Source line |
|---|-------------|----------------------|
| F1 | Authentification sécurisée des utilisateurs | SRS §2.1 |
| F2 | Déclenchement d'alertes SOS avec géolocalisation | SRS §2.2 |
| F3 | Assignation automatique du secouriste le plus proche | SRS §2.3 |
| F4 | Notification des zones de danger en temps réel | SRS §2.4 |
| F5 | Tableau de bord analytique pour la police | SRS §2.5 |

### 2.2 Non-functional requirements

- **Disponibilité :** Le système doit garantir un uptime de 99.9% grâce à la réplication Kubernetes.
- **Scalabilité :** Capacité à gérer 1000 alertes simultanées avec un temps de réponse < 500ms pour l'assignation.
- **Fiabilité :** Aucune perte d'alerte SOS grâce à la persistance Kafka (at-least-once).
- **Confidentialité :** Données chiffrées au repos et authentification JWT pour toutes les API.

### 2.3 Constraints

- **Infrastructure :** Doit s'exécuter sur un cluster Kubernetes. Risque : Complexité opérationnelle accrue.
- **Connectivité :** Gestion du mode hors-ligne. Risque : Désynchronisation des données si le réseau est instable.

## 3. Architectural Drivers & ASRs

1. **Fiabilité (Reliability) :** Une alerte SOS ne peut pas être perdue. C'est l'ASR prioritaire car des vies sont en jeu.
2. **Disponibilité (Availability) :** Le service doit être opérationnel 24/7, même pendant les mises à jour.
3. **Auditabilité :** Toutes les actions (alertes, assignations) doivent être tracées pour la police.

## 4. Component Identification

### 4.1 SRS-listed components
User Management, Emergency Component, Incident Report, Localization, Alert Management, Notification, Feedback, Analytics.

### 4.2 Your service decomposition
Nous avons décomposé le système en 5 microservices :
- `user-service` : Gère l'identité et les contacts.
- `sos-service` : Point d'entrée des alertes.
- `dispatch-service` : Cerveau de l'assignation et détection de zones.
- `notification-service` : Sortie vers les canaux de communication (SMS/Push).
- `analytics-service` : Agrégateur de données pour le reporting.

## 5. Architectural Style — Choice & Justification

Le style **Microservices Événementiels** (Event-Driven) a été choisi. 
- **Alternative 1 (Monolithe) :** Plus simple à développer mais difficile à scaler et point de défaillance unique (si le module de stats crash, tout tombe).
- **Alternative 2 (SOA synchrone) :** Trop de couplage. Si le service de notification est lent, il bloque l'assignation du secouriste. 

Le mode asynchrone via Kafka permet de décorréler la prise en charge de l'alerte de sa notification.

## 6. Architectural Patterns Applied

- **Saga (Choreography) :** Orchestre le flux de l'alerte à travers les services sans coordinateur central.
- **Circuit Breaker :** Protège les services contre les pannes de Kafka.
- **Strategy :** Permet de changer l'algorithme de matching à la volée (ex: MATCHER=nearest).

## 7. Architecture Decision Records (ADRs)

### ADR-001: Utilisation de Kafka pour la communication inter-services
- **Contexte :** Besoin d'une communication robuste et asynchrone.
- **Décision :** Utilisation de Kafka avec 3 partitions pour permettre le parallélisme.
- **Conséquences :** Complexité de configuration (Strimzi) mais haute résilience.

### ADR-002: Base de données SQLite par service avec PVC
- **Contexte :** Chaque service doit être autonome (Database-per-service).
- **Décision :** SQLite pour sa légèreté, monté sur des PersistentVolumeClaims Kubernetes.
- **Conséquences :** Facilité de test local, mais nécessite une gestion fine des volumes en production.

### ADR-003: Helm pour l'orchestration du déploiement
- **Contexte :** 5 services + Kafka + Monitoring à déployer.
- **Décision :** Création d'un Umbrella Chart.
- **Conséquences :** Déploiement en une seule commande (`helm install`).

## 8. Trade-offs & Improvement Perspectives

1. **Persistance :** Passer de SQLite à PostgreSQL géré (ex: Cloud SQL) pour une meilleure gestion des sauvegardes.
2. **Sécurité :** Implémenter mTLS entre les pods via un Service Mesh comme Istio.
3. **Observabilité :** Ajouter du traçage distribué (Jaeger) pour suivre une alerte à travers tous les services.
