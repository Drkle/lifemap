"""Crea índices E2 sin borrar ni modificar documentos; permite consultas vacías válidas."""
from comun import conectar


def main():
    client,db=conectar()
    try:
        db.reviews_live.create_index([('business_id',1),('fecha',1)])
        db.resenas.create_index([('business_id',1),('fecha',1)])
        for nombre in ('risk_scores','alerts'):
            db[nombre].create_index([('location','2dsphere')])
        db.live_windows.create_index([('centro','2dsphere')])
        db.live_windows.create_index([('location','2dsphere')])
        print('[entrega2] Índices verificados; no se borraron ni actualizaron documentos.')
    finally:
        client.close()


if __name__=='__main__':
    main()
