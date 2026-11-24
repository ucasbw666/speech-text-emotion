# voice-main integration

Source: https://github.com/willinger566/voice-main

Pinned commit: `538403fb1940895f443904c303a0b448bbf6ab93`.

The four inference runtime modules are adapted under `src/emotion_backend/`.
Changes: package-relative imports and streaming SHA256 compatible with Python 3.10.
The ensemble branches, feature extraction, preprocessing, classification weights,
probability calibration and segmentation retain the upstream implementation.
Production model artifacts are downloaded from the pinned commit and checked
against their Git LFS SHA256; the official emotion2vec+ large backbone is checked
against the checksum required by the trained classifier.

The upstream project does not declare a unified source-code license. This local
integration follows the user's request to combine their two course projects;
it does not assign a new license to the upstream code or model. Preserve the
included README, DATA_SOURCES and licenses when sharing course materials.
Models/data/openSMILE have their original research/noncommercial terms.
