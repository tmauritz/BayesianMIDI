import mido

def findDevices():
    print("Input Devices:")
    print(mido.get_input_names())
    print("Output Devices:")
    print(mido.get_output_names())

if __name__ == '__main__':
    findDevices()