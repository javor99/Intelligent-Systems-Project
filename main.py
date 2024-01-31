import subprocess
import serial
import requests
from picamera2 import Picamera2, Preview
import time
from shapely.geometry import Point, Polygon

# Function to fetch zone points from the endpoint
def fetch_zone_points(api_endpoint):
    try:
        response = requests.get(api_endpoint)
        if response.status_code == 200:
            zones = response.json()
            return zones
        else:
            print(f"Failed to fetch zone points. Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred while fetching zone points: {e}")
        return None



# Function to determine the zone for a given set of coordinates
def get_zone(lat, lon, zones):
    point = Point(lat,lon)
    print(str(point))

    for zone in zones:
        zone_coords = [(float(coord.split(',')[0]), float(coord.split(',')[1])) for coord in zone.values() if isinstance(coord, str) and ',' in coord]



        zone_polygon = Polygon(zone_coords)
        print(str(zone_polygon))

        if zone_polygon.contains(point):
            return zone["name"]
    
    return "Outside all zones"


api_endpoint = "https://x8ki-letl-twmt.n7.xano.io/api:ootQLWxx/zones"
zones = fetch_zone_points(api_endpoint)

print(str(zones))



def convert_nmea_to_decimal(gpgga_sentence):
    # Check if the sentence is a GPGGA sentence
    if not gpgga_sentence.startswith("$GPGGA"):
        return None

    # Split the GPGGA sentence into fields
    fields = gpgga_sentence.split(',')

    try:
        # Check for a valid fix status (fields[6])
        if fields[6] != '0':
            # Check for empty latitude and longitude fields
            if not fields[2] or not fields[4]:
                return None

            # Extract latitude and longitude values
            latitude = float(fields[2][:2]) + float(fields[2][2:]) / 60.0
            longitude = float(fields[4][:3]) + float(fields[4][3:]) / 60.0

            # Adjust latitude and longitude based on the hemisphere (N/S, E/W)
            if fields[3] == 'S':
                latitude = -latitude
            if fields[5] == 'W':
                longitude = -longitude

            return latitude, longitude
        else:
            # No valid fix, return None
            return None
    except ValueError:
        # Handle the case where conversion fails
        return None


# Xano API endpoint
api_url = "https://x8ki-letl-twmt.n7.xano.io/api:cJQUKsKf/cardata"

def capture_and_send_data():
    picam2 = Picamera2() 
    camera_config = picam2.create_still_configuration(main={"size": (1920, 1080)}, lores={"size": (640, 480)}, display="lores")
    picam2.configure(camera_config)
    picam2.start()




    while True:
        try:
            # Capture a picture
            picam2.capture_file("car.jpg")

            # Run ALPR to recognize the license plate
            print("picture succesfully taken")
            alpr_command = "alpr -c us,eu car.jpg"
            alpr_result = subprocess.run(alpr_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if alpr_result.returncode == 0:
                # Extract license plate from the first row of ALPR output
                output_lines = alpr_result.stdout.splitlines()
                print(output_lines)

                if isinstance(output_lines, list) and len(output_lines) > 1:
                # Results are available, extract the second element
                    license_plate = output_lines[1]

                else:
                    print("ALPR output is empty.")
                    license_plate = "UNKNOWN"

                # Open the serial port
                print("license plate is "+ license_plate)
                print("Opening serial port")
                ser = serial.Serial('/dev/ttyACM0', baudrate=9600, timeout=1)

                
                # Get GPS coordinates
                try:
                    while True:
                        # Read data from the serial port
                        data = ser.readline().decode('utf-8').strip()

                        # Try to convert the data to latitude and longitude
                        result = convert_nmea_to_decimal(data)

                        if result is not None:
                            # Successfully obtained latitude and longitude
                            latitude, longitude = result
                            print("GPS is working, longitude and latitude are "+ str(latitude) + " "+ str(longitude))

                            # Send data to the API
                            api_data = {
                                "license_plate": license_plate,
                                "latitude": str(latitude),
                                "longitude": str(longitude),
                                "zone": get_zone(latitude, longitude, zones)

                            }
                            print("Data packet being sent is " + str(api_data))
                            if(license_plate!="UNKNOWN"):

                                response = requests.post(api_url, json=api_data)
                                print("server response is " + str(response)) 
                                if response.status_code == 200:
                                    print("Data sent successfully to the API")
                                else:
                                    print(f"Failed to send data to the API. Status Code: {response.status_code}")

                            break

                except KeyboardInterrupt:
                    # Close the serial port on keyboard interrupt
                    ser.close()
                    print("Serial port closed.")

            else:
                print("ALPR failed")
                print("Error:")
                print(alpr_result.stderr)

            # Wait for a certain period before capturing the next picture
            time.sleep(1)  

        except Exception as e:
            print(f"An error occurred: {e}")

# Run the capture_and_send_data function indefinitely
while True:
    try:
        capture_and_send_data()
    except KeyboardInterrupt:
        print("Program terminated by the user.")
        break
    except Exception as e:
        print(f"An error occurred: {e}")
        




