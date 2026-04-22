import subprocess
import os

# 1. Configuración de rutas relativas
# Obtenemos la ruta de la carpeta donde está este script (src)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Subimos un nivel y entramos a /bin para hallar el adb.exe
ADB_BIN = os.path.join(BASE_DIR, "..", "bin", "adb.exe")
# Subimos un nivel y entramos a /server para el .jar
SERVER_JAR = os.path.join(BASE_DIR, "..", "server", "scrcpy-server.jar")

def ejecutar_adb(comando):
    """Función auxiliar para correr comandos ADB fácilmente"""
    try:
        # Ejecuta el comando y espera el resultado
        proceso = subprocess.run([ADB_BIN] + comando, capture_output=True, text=True)
        return proceso.stdout.strip()
    except FileNotFoundError:
        return "ERROR: No se encontró adb.exe en la carpeta /bin"

def test_conexion():
    print("--- Verificando conexión USB ---")
    
    # Paso A: Listar dispositivos
    dispositivos = ejecutar_adb(["devices"])
    print(dispositivos)

    if "device" not in dispositivos.split('\n')[1] if len(dispositivos.split('\n')) > 1 else False:
        print("\n[!] Error: No hay teléfonos detectados.")
        print("Revisa: 1. Cable conectado, 2. Depuración USB activa.")
        return

    # Paso B: Subir el servidor al móvil
    print("\n--- Subiendo servidor al teléfono ---")
    resultado_push = ejecutar_adb(["push", SERVER_JAR, "/data/local/tmp/scrcpy-server.jar"])
    print(resultado_push)
    print("\n[ÉXITO] El teléfono está listo para transmitir.")

if __name__ == "__main__":
    test_conexion()