[![Discord](https://img.shields.io/badge/chat-on%20discord-7289da.svg?sanitize=true)](https://discord.gg/GUAy9wErNu)
[![](https://img.shields.io/discord/908084610158714900)](https://discord.gg/GUAy9wErNu)
[![Static Badge](https://img.shields.io/badge/github-assemblyline-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline)
[![Static Badge](https://img.shields.io/badge/github-assemblyline\_service\_pixaxe-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline-service-pixaxe)
[![GitHub Issues or Pull Requests by label](https://img.shields.io/github/issues/CybercentreCanada/assemblyline/service-Pixaxe)](https://github.com/CybercentreCanada/assemblyline/issues?q=is:issue+is:open+label:service-Pixaxe)
[![License](https://img.shields.io/github/license/CybercentreCanada/assemblyline-service-pixaxe)](./LICENSE)
# Pixaxe Service

This Assemblyline service provides image analysis.

## Service Details

### Tesseract

This program is a Optical Character Recognition (OCR) engine, which attempts to extract text from images

Tesseract is licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)

Source code is found here: https://github.com/tesseract-ocr/tesseract

AL outputs:

- Text extracted and appended to file "output.txt"

#### OCR Configuration
In this service, you're allowed to override the default OCR terms from the [service base](https://github.com/CybercentreCanada/assemblyline-v4-service/blob/master/assemblyline_v4_service/common/ocr.py) using `ocr` key in the `config` block of the service manifest.

##### Simple Term Override (Legacy)
Let's say, I want to use a custom set of terms for `ransomware` detection. Then I can set the following:

```yaml
config:
    ocr:
        ransomware: ['bad1', 'bad2', ...]
```

This will cause the service to **only** use the terms I've specified when looking for `ransomware` terms. This is still subject to the hit threshold defined in the service base.

##### Advanced Term Override
Let's say, I want to use a custom set of terms for `ransomware` detection and I want to set the hit threshold to `1` instead of `2` (default). Then I can set the following:

```yaml
config:
    ocr:
        ransomware:
            terms: ['bad1', 'bad2', ...]
            threshold: 1
```

This will cause the service to **only** use the terms I've specified when looking for `ransomware` terms and is subject to the hit threshold I've defined.

##### Term Inclusion/Exclusion
Let's say, I want to add/remove a set of terms from the default set for `ransomware` detection. Then I can set the following:

```yaml
config:
    ocr:
        ransomware:
            include: ['bad1', 'bad2', ...]
            exclude: ['bank account']
```

This will cause the service to add the terms listed in `include` and remove the terms in `exclude` when looking for `ransomware` terms in OCR detection with the default set.


### Stenography Modules

*Please note that modules are optional (see service configuration). They are provided for academic purposes,
and are not considered ready for production environments*

Current AL modules:

Least significant bit (LSB) analysis:

- Visual attack

- Chi square

- LSB averages (idea from: http://guillermito2.net/stegano/tools/)

- Couples analysis (python code created largely from java code found here: https://github.com/b3dk7/StegExpose/blob/master/SamplePairs.java)

## Image variants and tags

Assemblyline services are built from the [Assemblyline service base image](https://hub.docker.com/r/cccs/assemblyline-v4-service-base),
which is based on Debian 11 with Python 3.11.

Assemblyline services use the following tag definitions:

| **Tag Type** | **Description**                                                                                  |      **Example Tag**       |
| :----------: | :----------------------------------------------------------------------------------------------- | :------------------------: |
|    latest    | The most recent build (can be unstable).                                                         |          `latest`          |
|  build_type  | The type of build used. `dev` is the latest unstable build. `stable` is the latest stable build. |     `stable` or `dev`      |
|    series    | Complete build details, including version and build type: `version.buildType`.                   | `4.5.stable`, `4.5.1.dev3` |

## Running this service

This is an Assemblyline service. It is designed to run as part of the Assemblyline framework.

If you would like to test this service locally, you can run the Docker image directly from the a shell:

    docker run \
        --name Pixaxe \
        --env SERVICE_API_HOST=http://`ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -f1 -d"/"`:5003 \
        --network=host \
        cccs/assemblyline-service-pixaxe

To add this service to your Assemblyline deployment, follow this
[guide](https://cybercentrecanada.github.io/assemblyline4_docs/developer_manual/services/run_your_service/#add-the-container-to-your-deployment).

## Documentation

General Assemblyline documentation can be found at: https://cybercentrecanada.github.io/assemblyline4_docs/

# Service Pixaxe

Ce service de la ligne d'assemblage fournit une analyse d'image.

## Détails du service

### Tesseract

Ce programme est un moteur de reconnaissance optique de caractères (OCR) qui tente d'extraire du texte à partir d'images.

Tesseract est soumis à la licence Apache, version 2.0 (http://www.apache.org/licenses/LICENSE-2.0).

Le code source se trouve ici : https://github.com/tesseract-ocr/tesseract

Résultats de l'AL :

- Texte extrait et ajouté au fichier « output.txt ».

#### Configuration de l'OCR
Dans ce service, vous êtes autorisé à remplacer les termes OCR par défaut de la [base du service] (https://github.com/CybercentreCanada/assemblyline-v4-service/blob/master/assemblyline_v4_service/common/ocr.py) en utilisant la clé `ocr` dans le bloc `config` du manifeste du service.

##### Remplacement d'un terme simple (héritage)
Supposons que je veuille utiliser un ensemble de termes personnalisés pour la détection de `ransomware`. Je peux alors définir ce qui suit :

```yaml
config :
    ocr :
        ransomware : ['bad1', 'bad2', ...]
```

Ainsi, le service utilisera **uniquement** les termes que j'ai spécifiés lorsqu'il cherchera des termes de `ransomware`. Ceci est toujours soumis au seuil de réussite défini dans la base du service.

##### Remplacement des termes avancés
Supposons que je veuille utiliser un ensemble personnalisé de termes pour la détection de `ransomware` et que je veuille fixer le seuil de réussite à `1` au lieu de `2` (par défaut). Je peux alors définir ce qui suit :

```yaml
config :
    ocr :
        ransomware :
            terms : ['bad1', 'bad2', ...]
            threshold : 1
```

Le service utilisera **uniquement** les termes que j'ai spécifiés lors de la recherche de termes `ransomware` et sera soumis au seuil de réponse que j'ai défini.

##### Inclusion/exclusion de termes
Supposons que je veuille ajouter/supprimer un ensemble de termes de l'ensemble par défaut pour la détection de `ransomware`. Je peux alors définir ce qui suit :

```yaml
config :
    ocr :
        ransomware :
            include : ['bad1', 'bad2', ...]
            exclude : ['bank account']
```

Ainsi, le service ajoutera les termes listés dans `include` et supprimera les termes dans `exclude` lorsqu'il recherchera les termes `ransomware` dans la détection OCR avec le paramétrage par défaut.


### Modules de sténographie

*Veuillez noter que les modules sont optionnels (voir la configuration du service). Ils sont fournis à des fins académiques,
et ne sont pas considérés comme prêts pour des environnements de production*

Modules AL actuels :

Analyse du bit le moins significatif (LSB) :

- Attaque visuelle

- Khi carré

- Moyennes LSB (idée tirée de : http://guillermito2.net/stegano/tools/)

- Analyse de couples (code python créé en grande partie à partir du code java trouvé ici : https://github.com/b3dk7/StegExpose/blob/master/SamplePairs.java)

Traduit avec DeepL.com (version gratuite)

## Variantes et étiquettes d'image

Les services d'Assemblyline sont construits à partir de l'image de base [Assemblyline service](https://hub.docker.com/r/cccs/assemblyline-v4-service-base),
qui est basée sur Debian 11 avec Python 3.11.

Les services d'Assemblyline utilisent les définitions d'étiquettes suivantes:

| **Type d'étiquette** | **Description**                                                                                                |  **Exemple d'étiquette**   |
| :------------------: | :------------------------------------------------------------------------------------------------------------- | :------------------------: |
|   dernière version   | La version la plus récente (peut être instable).                                                               |          `latest`          |
|      build_type      | Type de construction utilisé. `dev` est la dernière version instable. `stable` est la dernière version stable. |     `stable` ou `dev`      |
|        série         | Détails de construction complets, comprenant la version et le type de build: `version.buildType`.              | `4.5.stable`, `4.5.1.dev3` |

## Exécution de ce service

Il s'agit d'un service d'Assemblyline. Il est optimisé pour fonctionner dans le cadre d'un déploiement d'Assemblyline.

Si vous souhaitez tester ce service localement, vous pouvez exécuter l'image Docker directement à partir d'un terminal:

    docker run \
        --name Pixaxe \
        --env SERVICE_API_HOST=http://`ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -f1 -d"/"`:5003 \
        --network=host \
        cccs/assemblyline-service-pixaxe

Pour ajouter ce service à votre déploiement d'Assemblyline, suivez ceci
[guide](https://cybercentrecanada.github.io/assemblyline4_docs/fr/developer_manual/services/run_your_service/#add-the-container-to-your-deployment).

## Documentation

La documentation générale sur Assemblyline peut être consultée à l'adresse suivante: https://cybercentrecanada.github.io/assemblyline4_docs/
