# ETERNA Backend V7 Scaffold

Backend mínimo desplegable para ETERNA con FastAPI.

## Qué hace
- Crea pedidos
- Simula pago ya confirmado
- Genera un vídeo placeholder con FFmpeg
- Expone el vídeo final

## Importante
Este proyecto es un **scaffold** para arrancar rápido.
Tu pipeline cinematográfico real debe reemplazar `app/services/video_engine.py`.

## Endpoints
- `GET /healthz`
- `POST /orders`
- `GET /orders/{order_uuid}`
- `GET /video/{order_uuid}`

## Payload de ejemplo
```json
{
  "customer_name": "Sergio",
  "customer_email": "sergio@example.com",
  "recipient_name": "Papá",
  "phrases": ["Gracias por estar", "Siempre conmigo", "Te quiero"],
  "photo_links": [
    "https://example.com/foto1.jpg",
    "https://example.com/foto2.jpg",
    "https://example.com/foto3.jpg"
  ],
  "surprise_message": "Con cariño",
  "is_sender_reaction_enabled": false
}
```
