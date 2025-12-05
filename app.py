
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# 1) UNA sola instancia global de SQLAlchemy (sin registrar aún la app)
db = SQLAlchemy()

# 2) Modelo de mediciones
class Measurement(db.Model):
    __tablename__ = 'measurements'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    value = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Measurement {self.id} @ {self.timestamp} = {self.value}>'

def create_app():
    app = Flask(__name__)

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'temperature.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 3) Registrar la extensión UNA sola vez
    db.init_app(app)

    # 4) Inicializar tablas al arrancar (sin before_first_request)
    with app.app_context():
        db.create_all()

    # =========================
    # Rutas
    # =========================
    @app.route('/', methods=['GET'])
    def index():
        measurements = Measurement.query.order_by(Measurement.timestamp.asc()).all()
        labels = [m.timestamp.strftime('%Y-%m-%d %H:%M:%S') for m in measurements]
        values = [m.value for m in measurements]
        return render_template('index.html', labels=labels, values=values)


    @app.route('/api/measurements/add', methods=['GET'])
    def add_measurement_via_get():
        """
        Permite crear una medición vía GET.
        Ejemplos:
          /api/measurements/add?value=25.7
          /api/measurements/add?value=25.7&timestamp=2025-12-05 12:34:56
          /api/measurements/add?value=25.7&timestamp=2025-12-05T12:34:56

        Params:
          - value: float (requerido)
          - timestamp: str (opcional; 'YYYY-mm-dd HH:MM:SS' o ISO 8601 sin zona)
        """
        # 1) Leer params
        val_str = request.args.get('value', default=None, type=str)
        ts_str = request.args.get('timestamp', default=None, type=str)

        if val_str is None:
            return jsonify({"error": "Falta el parámetro 'value' en query string"}), 400

        # 2) Validar value
        try:
            value = float(val_str)
        except (TypeError, ValueError):
            return jsonify({"error": "'value' debe ser numérico"}), 400

        # 3) Parsear timestamp (opcional)
        if ts_str:
            # Admitimos dos formatos: 'YYYY-mm-dd HH:MM:SS' y 'YYYY-mm-ddTHH:MM:SS'
            try:
                timestamp = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    timestamp = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    return jsonify({"error": "Formato 'timestamp' inválido. Usa 'YYYY-mm-dd HH:MM:SS' o ISO 8601 simple."}), 400
        else:
            timestamp = datetime.now()

        # 4) Crear y guardar
        m = Measurement(timestamp=timestamp, value=value)
        db.session.add(m)
        db.session.commit()

        # 5) Responder
        return jsonify({
            "id": m.id,
            "timestamp": m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "value": m.value
        }), 201


    @app.route('/api/measurements', methods=['POST'])
    def create_measurement():
        """
        Espera JSON:
        {
          "value": 25.7,                 // requerido
          "timestamp": "2025-12-05 12:34:56"  // opcional (si no, se usa now())
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON inválido o vacío"}), 400

        if 'value' not in data:
            return jsonify({"error": "Falta 'value' en el payload"}), 400

        try:
            value = float(data['value'])
        except (TypeError, ValueError):
            return jsonify({"error": "'value' debe ser numérico"}), 400

        ts = data.get('timestamp')
        if ts:
            try:
                timestamp = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    timestamp = datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    return jsonify({"error": "Formato 'timestamp' inválido. Usa 'YYYY-mm-dd HH:MM:SS' o ISO 8601."}), 400
        else:
            timestamp = datetime.now()

        m = Measurement(timestamp=timestamp, value=value)
        db.session.add(m)
        db.session.commit()

        return jsonify({
            "id": m.id,
            "timestamp": m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "value": m.value
        }), 201

    @app.route('/api/measurements', methods=['GET'])
    def list_measurements():
        limit = request.args.get('limit', type=int)
        order = request.args.get('order', default='asc', type=str)

        q = Measurement.query
        q = q.order_by(Measurement.timestamp.desc() if order == 'desc' else Measurement.timestamp.asc())
        if limit:
            q = q.limit(limit)

        rows = q.all()
        return jsonify([
            {"id": r.id, "timestamp": r.timestamp.strftime('%Y-%m-%d %H:%M:%S'), "value": r.value}
            for r in rows
        ])

    @app.route('/api/measurements/<int:id>', methods=['DELETE'])
    def delete_measurement(id):
        m = Measurement.query.get_or_404(id)
        db.session.delete(m)
        db.session.commit()
        return jsonify({"status": "deleted", "id": id})

    return app

# 5) Crear la app (import-safe)
app = create_app()

if __name__ == '__main__':
    # Importante: desactivar el reloader si notas doble ejecución
    app.run(debug=True, use_reloader=False)
