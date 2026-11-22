# Robot Paletleme & Hat Sonu RFQ Asistanı (Streamlit Demo)

Satış ekibinin müşteri görüşmelerinde hızlıca teknik veri toplayıp otomatik olarak **Kolaboratif** veya **Endüstriyel** robot önerisi, görsel ekipman özeti, alan hesabı ve satış fiyatlaması alabileceği 3 sayfalık Streamlit uygulamasıdır.

## Klasör Yapısı

```text
robot_rfq_demo/
├── app.py
├── requirements.txt
├── README.md
└── assets/
    ├── cobot.png
    ├── industrial.png
    ├── gripper_vakum.png
    ├── gripper_yandan.png
    ├── gripper_alttan.png
    ├── strec_tam_otomatik.png
    └── strec_yari_otomatik.png
```

## Kurulum ve Çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Karar Kuralları ve Ham Maliyetler

- **Robot Tipi:** Ürün ağırlığı `> 12 kg` **veya** kapasite `> 10 ürün/dk` ise **Endüstriyel Tip Robot** (`80.000 €`, güvenlik çiti dahil, `4.2 m × 4.2 m`); her iki değer de eşik değerlerin altında/dahilindeyse **Kolaboratif Tip Robot** (`90.000 €`, çit gerekmez, `1.5 m × 0.75 m`).
- **Streçleme:** Tam Otomatik (`100.000 €`, `5.0 m × 7.0 m`) veya Yarı Otomatik (`40.000 €`, `2.0 m × 2.0 m`).
- **Kapsam Dışı Kalemler:** Palet konveyörleri, ürün biriktirme konveyörleri, reject sistemi, ek güvenlik ve yazılım ekipmanları.
