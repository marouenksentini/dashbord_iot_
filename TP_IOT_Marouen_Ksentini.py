import time
import requests
import random

# ==============================================================================
# 1. GESTION DE L'ENVIRONNEMENT (PC vs Raspberry Pi)
# ==============================================================================
# Ce bloc détecte automatiquement si le script s'exécute sur un vrai Raspberry Pi.
# Si on est sur PC, la bibliothèque RPi.GPIO n'existe pas. On capture l'erreur (except)
# pour éviter que le programme ne plante, permettant ainsi de tester le code sur PC.
try:
    import RPi.GPIO as GPIO  
    GPIO.setmode(GPIO.BCM) # Utilisation de la numérotation des broches du processeur (BCM)
    IS_RPI = True
except (ImportError, RuntimeError):
    IS_RPI = False

# ==============================================================================
# 2. CONFIGURATION UBIDOTS & MATÉRIEL
# ==============================================================================
# Votre jeton (Token) API secret pour vous authentifier auprès d'Ubidots
TOKEN = "BBUS-Gc3PS5ZCWc8UaSzXFI6es90eHzDJz0"  
# Le nom de votre appareil tel qu'il apparaîtra sur Ubidots
DEVICE_LABEL = "berry"

# Les variables associées à votre appareil sur le tableau de bord Ubidots
VARIABLE_LABEL_1 = "temperature"
VARIABLE_LABEL_2 = "humidite"
VARIABLE_LABEL_3 = "position"
VARIABLE_SWITCH = "vuntulator"  # Interrupteur virtuel pour contrôler le ventilateur

# Utilisation directe de l'adresse IP d'Ubidots pour éviter les pannes de serveur DNS
UBIDOTS_IP = "169.55.61.243"
RELAY_PIN = 3 # La broche physique GPIO 3 du Raspberry Pi connectée au relais du ventilateur

# Initialisation des composants matériels si nous sommes sur un Raspberry Pi
if IS_RPI:
    try:
        GPIO.setup(RELAY_PIN, GPIO.OUT)       # Configure la broche 3 comme une SORTIE
        GPIO.output(RELAY_PIN, GPIO.LOW)      # Initialise la broche à l'état BAS (Éteint)
        print("🔌 [MATÉRIEL] Mode Raspberry Pi détecté. Broche GPIO 3 configurée.")
    except Exception as e:
        print(f"⚠️ Erreur d'initialisation GPIO, bascule en simulation : {e}")
        IS_RPI = False
else:
    print("💻 [SIMULATION] Exécution sur PC détectée. Le ventilateur sera simulé dans la console.")

# ==============================================================================
# 3. CRÉATION DES DONNÉES (Payload Builder)
# ==============================================================================
def build_payload(variable_1, variable_2, variable_3, variable_4):
    """
    Génère des valeurs aléatoires pour simuler de vrais capteurs environnementaux.
    Ajoute également des coordonnées GPS fixes (Région de Sfax, Tunisie).
    """
    value_1 = random.randint(30, 81)   # Simule une température entre 30°C et 81°C
    value_2 = random.randint(50, 71)   # Simule un taux d'humidité entre 50% et 71%
    value_4 = random.choice([0, 1])    # Simule une valeur binaire aléatoire

    # Coordonnées géographiques pour afficher l'appareil sur la carte Ubidots
    lat = 34.7406
    lng = 10.7603

    # Organisation des données selon le format d'API JSON strict exigé par Ubidots
    payload = {
        variable_1: value_1,
        variable_2: value_2,
        variable_4: value_4,
        variable_3: 1,         # Valeur pivot requise pour déclencher l'affichage GPS
        "$lat": lat,           # Syntaxe spéciale Ubidots pour la Latitude
        "$lng": lng            # Syntaxe spéciale Ubidots pour la Longitude
    }
    
    print(f"\n📊 [CAPTEURS] Temp: {value_1}°C | Humidité: {value_2}% | Sim Switch ({variable_4}): {value_4} | GPS: {lat}, {lng}")
    return payload

# ==============================================================================
# 4. COMMUNICATION RÉSEAU (HTTP POST & GET)
# ==============================================================================
def post_request(payload):
    """
    Gère la partie réseau : Envoie les données vers Ubidots (POST) et 
    récupère l'état de l'interrupteur à distance (GET).
    """
    # URL pour envoyer (pousser) les données de l'appareil
    url_post = f"http://{UBIDOTS_IP}/api/v1.6/devices/{DEVICE_LABEL}"
    # URL pour lire la dernière valeur ("lv" = latest value) de l'interrupteur du ventilateur
    url_get = f"http://{UBIDOTS_IP}/api/v1.6/devices/{DEVICE_LABEL}/{VARIABLE_SWITCH}/lv"
    
    # En-têtes HTTP requis contenant l'authentification
    headers = {
        "X-Auth-Token": TOKEN,
        "Content-Type": "application/json"
    }

    # ---- ÉTAPE 4a : ENVOI DES DONNÉES DES CAPTEURS (POST) ----
    try:
        # Envoi de la requête avec un "timeout" de 5 secondes pour éviter que le script ne bloque si internet coupe
        req = requests.post(url=url_post, headers=headers, json=payload, timeout=5)
        if req.status_code < 400:
            print(f"[INFO] Données envoyées avec succès (Code HTTP: {req.status_code})")
        else:
            print(f"[WARNING] Réponse du serveur Ubidots (Code HTTP: {req.status_code})")
    except Exception as e:
        print(f"[WARNING] Échec de l'envoi des capteurs : {e}")

    # ---- ÉTAPE 4b : LECTURE DE L'INTERRUPTEUR CLOUD & ACTION (GET) ----
    try:
        req_get = requests.get(url=url_get, headers=headers, timeout=5)
        if req_get.status_code == 200:
            # Le serveur renvoie la valeur brute sous forme de texte (ex: "1.0" ou "0.0")
            valeur_bouton = float(req_get.text)
            
            if valeur_bouton == 1.0:
                print(f"🟢 [CONSOLE] Variable '{VARIABLE_SWITCH}' sur Ubidots : ON (1.0)")
                print(f"⚙️ [ACTION] Port GPIO {RELAY_PIN} à l'état HAUT (Ventilateur en MARCHE)")
                if IS_RPI:
                    GPIO.output(RELAY_PIN, GPIO.HIGH) # Envoie du 3.3V pour activer le relais
            elif valeur_bouton == 0.0:
                print(f"🔴 [CONSOLE] Variable '{VARIABLE_SWITCH}' sur Ubidots : OFF (0.0)")
                print(f"⚙️ [ACTION] Port GPIO {RELAY_PIN} à l'état BAS (Ventilateur ARRÊTÉ)")
                if IS_RPI:
                    GPIO.output(RELAY_PIN, GPIO.LOW)  # Coupe le courant pour couper le relais
        else:
            print(f"[WARNING] Impossible de lire la variable '{VARIABLE_SWITCH}' (Code HTTP: {req_get.status_code})")
            
    except Exception as e:
        print(f"[WARNING] Erreur lors de la récupération de la télécommande vuntulator : {e}")

# ==============================================================================
# 5. BOUCLE PRINCIPALE D'ARRIVÉE ET D'EXÉCUTION
# ==============================================================================
def main():
    """Regroupe la création du payload et son envoi réseau."""
    payload = build_payload(
        VARIABLE_LABEL_1,
        VARIABLE_LABEL_2,
        VARIABLE_LABEL_3,
        VARIABLE_SWITCH
    )
    post_request(payload)

if __name__ == '__main__':
    try:
        print(f"\n🚀 Système IoT Initialisé (Label 4 actif: {VARIABLE_SWITCH}).")
        print("Envoi actif et lecture de l'IHM toutes les 30 secondes.")
        print("Appuyez sur Ctrl+C pour quitter le script.\n")
        
        while True:
            main()
            # 🛠️ CORRECTION DU TAUX DE REQUÊTES : Essentiel pour éviter l'erreur "HTTP 429 Too Many Requests".
            # Les comptes gratuits Ubidots limitent le nombre de requêtes par minute. Attendre 30s permet de respecter les quotas.
            print("[INFO] En attente de 30 secondes...\n")
            time.sleep(30)
            
    except KeyboardInterrupt:
        # Permet d'arrêter proprement le script dans le terminal avec Ctrl+C
        print("\n🛑 Le script a été arrêté proprement.")
    finally:
        # IMPORTANT : Réinitialise l'état des broches du Raspberry Pi à la fermeture.
        # Cela évite de laisser une broche active par accident ou de causer un court-circuit.
        if IS_RPI:
            GPIO.cleanup()
            print("🧹 Nettoyage des broches GPIO effectué.")