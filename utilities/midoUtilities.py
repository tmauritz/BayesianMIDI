import mido

def findDevices():
    print(mido.get_input_names())

if __name__ == '__main__':
    findDevices()