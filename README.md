# Sasquatch

An iOS swift app that automatically generates climbing routes from pictures/LiDAR scans of spray walls. Developed for [Produhacks 2026](https://devpost.com/software/sasquatch).

<img width="288" height="573" alt="image" src="https://github.com/user-attachments/assets/296125fc-bb6f-4f56-b774-ece0a294005a" />
<img width="264" height="573" alt="image" src="https://github.com/user-attachments/assets/03ac8bcb-a896-4532-9cc2-3ae51ae78504" />

Pipeline: iOS app (SwiftUI + LiDAR) → PLY + image upload to Google Cloud Storage → FastAPI backend → Detectron2 hold detection → Gemini API classification → PostgreSQL storage → route generation → back to client for visualization.

Built with SwiftUI, Python, FastAPI, PyTorch/Detectron2, SQLAlchemy, PostgreSQL, Google Cloud (GCS + Cloud SQL + OAuth2), and Docker.

