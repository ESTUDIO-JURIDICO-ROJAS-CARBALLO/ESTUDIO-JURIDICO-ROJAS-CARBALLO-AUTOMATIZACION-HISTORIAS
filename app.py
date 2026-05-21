import os
import threading
from flask import Flask, render_template, request, jsonify, send_file
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
from bot import obtener_noticia_cordoba, crear_imagen_historia, publicar_en_instagram
import pytz

app = Flask(__name__)

# Logs en memoria (para mostrar en la web)
logs = []

def add_log(msg):
    tz = pytz.timezone('America/Argentina/Cordoba')
    timestamp = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    logs.insert(0, f"[{timestamp}] {msg}")
    print(f"[{timestamp}] {msg}")

# Estado del planificador
scheduler = BackgroundScheduler(timezone=pytz.timezone('America/Argentina/Cordoba'))
scheduler_job = None
AUTO_PUBLISH_TIME = "10:00" # Por defecto

def job_publicar_diario():
    add_log("=== INICIANDO PUBLICACIÓN AUTOMÁTICA DIARIA ===")
    ejecutar_bot()

def ejecutar_bot():
    try:
        add_log("Buscando noticias legales en Google News...")
        noticia = obtener_noticia_cordoba()
        if noticia:
            add_log(f"Noticia encontrada: {noticia['titulo']}")
            add_log("Generando diseño de historia en PNG...")
            img_path = crear_imagen_historia(noticia)
            add_log("Imagen generada correctamente.")
            
            add_log("Publicando en Instagram...")
            publicar_en_instagram(noticia, img_path)
            add_log("¡Proceso finalizado con éxito! Historia publicada.")
            return True, "Historia publicada con éxito."
        else:
            add_log("No se encontraron noticias relevantes hoy.")
            return False, "No se encontraron noticias."
    except Exception as e:
        add_log(f"ERROR: {str(e)}")
        return False, f"Error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html', logs=logs, auto_time=AUTO_PUBLISH_TIME, is_running=scheduler.running)

@app.route('/api/status')
def status():
    return jsonify({
        "is_running": scheduler.running,
        "logs": logs[:20] # últimos 20 logs
    })

@app.route('/api/start', methods=['POST'])
def start_scheduler():
    global AUTO_PUBLISH_TIME, scheduler_job
    data = request.json
    AUTO_PUBLISH_TIME = data.get('time', '10:00')
    
    hour, minute = map(int, AUTO_PUBLISH_TIME.split(':'))
    
    if scheduler.running:
        scheduler.shutdown()
        
    scheduler.start()
    
    if scheduler_job:
        scheduler_job.remove()
        
    scheduler_job = scheduler.add_job(job_publicar_diario, 'cron', hour=hour, minute=minute)
    add_log(f"Planificador INICIADO. Próxima publicación a las {AUTO_PUBLISH_TIME}.")
    
    return jsonify({"success": True})

@app.route('/api/stop', methods=['POST'])
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
    add_log("Planificador DETENIDO.")
    return jsonify({"success": True})

@app.route('/api/force_publish', methods=['POST'])
def force_publish():
    # Ejecutamos en un hilo separado para no bloquear la web
    add_log("Ejecución manual iniciada...")
    thread = threading.Thread(target=ejecutar_bot)
    thread.start()
    return jsonify({"success": True, "message": "Iniciando publicación en segundo plano."})

@app.route('/preview')
def preview():
    # Retorna la última imagen generada si existe (usando ruta absoluta)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(base_dir, 'story_final.png')
    if os.path.exists(img_path):
        return send_file(img_path, mimetype='image/png')
    else:
        return "No hay imagen generada aún.", 404

if __name__ == '__main__':
    add_log("Servidor iniciado. Esperando instrucciones...")
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
