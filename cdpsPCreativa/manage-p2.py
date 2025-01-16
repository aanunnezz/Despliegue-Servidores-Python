#!/usr/bin/env python

from lib_vm import VM, Red
import logging, sys
import os
import json
from lxml import etree
from subprocess import call

# 1er paso: comprobamos de manage-p2.json q el nº de servidores es correcto y vemos si está en modo debug
with open('manage-p2.json', 'r') as file: 
    config = json.load(file)

    if config["number_of_servers"] > 5 or config["number_of_servers"] < 1:
        print("Nº de servidores incorrecto")
    else:
        num_serv = config["number_of_servers"]

    debug = config["debug"]
    if debug == True:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


def init_log():
    # Creacion y configuracion del logger
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger('auto_p2')
    ch = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', "%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    log.addHandler(ch)
    log.propagate = False

# Ahora había que cambiar el nombre, la ruta de archivo y la interfaz bridge
# Sustituya en la plantilla todos los campos marcados con XXX por los valores que
# correspondan en cada caso. Tenga en cuenta que:
# • Los nombres de los bridges que soportan cada una de las LAN son LAN1 y LAN2.
# • Se utilizarán bridges basados en la solución de Open Virtual Switch (OVS). Para
# ello, deberá incluir la etiqueta resaltada en las secciones <interface> del fichero
# XML de especificación de cada MV:
def edit_xml(mv):

    if mv == "c1" or "lb":
        bridgeAux = "LAN1"
    else:
        bridgeAux = "LAN2"    

    cwd = os.getcwd()  # directorio actual
    dir = cwd + "/" + mv  # directorio de la máquina virtual que toque

    tree = etree.parse(dir + ".xml")  # parseamos el xml
    root = tree.getroot()  # obtenemos el root del xml

    name = root.find("name")
    name.text = mv

    source = root.find("./devices/disk/source")
    source.set("file", dir + ".qcow2")
    bridge = root.find("./devices/interface/source")
    bridge.set("bridge", bridgeAux)  # buscamos y cambiamos los atributos nombre, la ruta y el bridge por los que toquen
    if mv == "lb":
        element = etree.Element("interface")
        aux = root.find("devices")
        aux.append(element)
        element.set('type', "bridge")
        etree.SubElement(element, "source", bridge="LAN2")
        etree.SubElement(element, "model", type="virtio")

    fout = open(dir + ".xml", "w")
    fout.write(etree.tounicode(tree, pretty_print=True))
    fout.close()  # lb tiene las 2 interfaces, con el método anterior solo se añade una


# En este punto toca la configuración de red de cada una de las máquinas virtuales
# Una vez arrancadas las máquinas virtuales, proceda a cambiarles el nombre modificando
# el fichero /etc/hostname. Para ello entre en la consola con usuario cdps y, por ejemplo,
# para s1 ejecute: sudo bash -c "echo s1 > /etc/hostname"

def config(mv):    
    cwd = os.getcwd()
    path = cwd + "/" + mv 
    
    fout = open("hostname",'w')  #abrimos hostname en modo escritura y añadimos el nombre de la mv parámetro
    fout.write(mv + "\n")  
    fout.close()

    # Por ejemplo, para copiar el fichero hostname
    # al directorio /etc de la imagen s1.qcow2 utilizada en la VM s1:
    # sudo virt-copy-in -a s1.qcow2 hostname /etc 

    call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "hostname", "/etc"])

    # Edite, además, el fichero /etc/hosts y cambie la entrada asociada a la dirección 127.0.1.1
    # por el nombre de cada máquina. Por ejemplo, para s1:
    # 127.0.1.1 s1
    fout = open("hosts",'w')
    fout.write("127.0.1.1" + " " + mv + "\n")
    fout.close()

    call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "hosts", "/etc"])  # copia el fichero hosts en la máquina virtual

    fout = open("interfaces",'w')  # abrimos interfaces en modo escritura y añadimos la configuración de red
    if mv == "lb":
        fout.write("auto lo\n")
        fout.write("iface lo inet loopback\n\n")
        
        fout.write("auto eth0\n")
        fout.write("iface eth0 inet static\n")
        fout.write("    address 10.1.1.1\n")
        fout.write("    netmask 255.255.255.0\n\n")
        
        fout.write("auto eth1\n")
        fout.write("iface eth1 inet static\n")
        fout.write("    address 10.1.2.1\n")
        fout.write("    netmask 255.255.255.0\n")

    if mv == "c1":      # en esquema c1 tiene la ip .2
        fout.write("auto lo\n")
        fout.write("iface lo inet loopback\n\n")
        
        fout.write("auto eth0\n")
        fout.write("iface eth0 inet static\n")
        fout.write("    address 10.1.1.2\n")
        fout.write("    netmask 255.255.255.0\n\n")

    else:
        fout.write("auto lo\n")
        fout.write("iface lo inet loopback\n\n")
        
        fout.write("auto eth0\n")
        fout.write("iface eth0 inet static\n")
        fout.write("    address 10.1.2.11\n")
        fout.write("    netmask 255.255.255.0\n")
        fout.write("    gateway 10.1.2.1\n")

    fout.close()

    # Por ejemplo, para copiar el fichero interfaces
    # al directorio /etc/network de la imagen s1.qcow2 utilizada en la VM s1:
    # sudo virt-copy-in -a s1.qcow2 interfaces /etc/network 
    call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "interfaces", "/etc/network"])

    # Para que el balanceador de tráfico funcione como router al arrancar, se recomienda
    # editar el fichero /etc/sysctl.conf tal como se describe en
    # http://www.ducea.com/2006/08/01/how-to-enable-ip-forwarding-in-linux/. Para ello
    # puede utilizar el siguiente comando: sudo virt-edit -a lb.qcow2 /etc/sysctl.conf -e 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/'
    if mv == "lb":
        call(["sudo", "virt-edit", "-a", mv + ".qcow2", "/etc/sysctl.conf", "-e", "s/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/"])

def pause():
    programPause = input("-- Press <ENTER> to continue...")

# Main
init_log()

param = sys.argv[1]

if param == "create":

    lb =  VM("lb")
    lb.create_vm()
    
    c1 = VM("c1")
    c1.create_vm()

    for i in range(1, num_serv+1):
        mv = VM("s"+str(i))
        mv.create_vm()

elif param == "start":

    lb =  VM("lb")
    lb.start_vm()
    lb.show_console_vm()

    c1 = VM("c1")
    c1.start_vm()
    c1.show_console_vm()
    for i in range(1, num_serv+1):
        mv = VM("s"+str(i))
        mv.start_vm()
        mv.show_console_vm()

elif param == "stop":
    lb =  VM("lb")
    lb.stop_vm()
    c1 = VM("c1")
    c1.stop_vm()
    for i in range(1, num_serv+1):
        mv = VM("s"+str(i))
        mv.stop_vm()

elif param == "destroy":
    lb =  VM("lb")
    lb.destroy_vm()
    c1 = VM("c1")
    c1.destroy_vm()
    for i in range(1, num_serv+1):
        mv = VM("s"+str(i))
        mv.destroy_vm()

else: print("Comando no válido, escriba: 'create, start, stop o destroy'")

