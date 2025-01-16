import logging
import os
import subprocess
from lxml import etree

log = logging.getLogger('manage-p2')

# Ahora había que cambiar el nombre, la ruta de archivo y la interfaz bridge.
# Sustituya en la plantilla todos los campos marcados con XXX por los valores que
# correspondan en cada caso. Tenga en cuenta que:
# • Los nombres de los bridges que soportan cada una de las LAN son LAN1 y LAN2.
# • Se utilizarán bridges basados en la solución de Open Virtual Switch (OVS). 
# Para ello, deberá incluir la etiqueta resaltada en las secciones <interface> 
# del fichero XML de especificación de cada MV:

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

    fout = open("hostname", 'w')  # Abrimos hostname en modo escritura y añadimos el nombre de la mv parámetro
    fout.write(mv + "\n")  
    fout.close()

    # Por ejemplo, para copiar el fichero hostname
    # al directorio /etc de la imagen s1.qcow2 utilizada en la VM s1:
    # sudo virt-copy-in -a s1.qcow2 hostname /etc 
    subprocess.call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "hostname", "/etc"])

    # Edita, además, el fichero /etc/hosts y cambia la entrada asociada a la dirección 127.0.1.1
    # por el nombre de cada máquina. Por ejemplo, para s1:
    # 127.0.1.1 s1
    fout = open("hosts", 'w')
    fout.write("127.0.1.1" + " " + mv + "\n")
    fout.close()

    subprocess.call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "hosts", "/etc"])  # Copia el fichero hosts en la máquina virtual

    fout = open("interfaces", 'w')  # Abrimos interfaces en modo escritura y añadimos la configuración de red
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

    if mv == "c1":      # En esquema c1 tiene la ip .2
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
    subprocess.call(["sudo", "virt-copy-in", "-a", mv + ".qcow2", "interfaces", "/etc/network"])

class VM:
    def __init__(self, name):
        self.name = name
        log.debug('init VM ' + self.name)

    def create_vm(self ):
        # qemu-img create -F qcow2 -f qcow2 -b cdps-vm-base-pc1.qcow2 s1.qcow2 
        subprocess.call(["qemu-img", "create", "-F", "qcow2", "-f", "qcow2", "-b", "cdps-vm-base-pc1.qcow2", self.name + ".qcow2"])
        # cp plantilla-vm-pc1.xml s1.xml
        subprocess.call(["cp", "plantilla-vm-pc1.xml", self.name + ".xml"])
        # Sustituya en la plantilla todos los campos marcados con XXX
        edit_xml(self.name)
        subprocess.call(["sudo", "virsh", "define", self.name + ".xml"])
        log.debug("Machine " + self.name + " defined.")
        ##!!!!HACER CONFIG(self)
        config(self.name)

    def start_vm(self):
        log.debug("start_vm " + self.name)
        subprocess.call(["sudo", "virsh", "start", self.name])
        log.debug(self.name + " started successfully")

    def show_console_vm(self):
        log.debug("show_console_vm " + self.name)
        subprocess.call(["xterm", "-e", "sudo", "virsh", "console", self.name])

    def stop_vm(self):
        log.debug("stop_vm " + self.name)
        subprocess.call(["sudo", "virsh", "shutdown", self.name])
        log.debug(self.name + " stopped successfully")

    def destroy_vm(self):
        log.debug("destroy_vm " + self.name)
        subprocess.call(["sudo", "virsh", "destroy", self.name])
        log.debug(self.name + " destroyed")

class Red:
    def __init__(self, name):
        self.name = name
        log.debug('init net ' + self.name)

    def create_net(self):
        log.debug('create_net ' + self.name)
        subprocess.call(["sudo", "ovs-vsctl", "addbr", "LAN1"])
        subprocess.call(["sudo", "ovs-vsctl", "addbr", "LAN2"])
        subprocess.call(["sudo", "ifconfig", "LAN1", "up"])
        subprocess.call(["sudo", "ifconfig", "LAN2", "up"])
        subprocess.call(["sudo", "ifconfig", "LAN1", "10.1.1.3/24"])
        subprocess.call(["sudo", "ip", "route", "add", "10.1.0.0/16", "via", "10.1.1.1"])
        log.debug(self.name + ' created')

    def destroy_net(self):
        log.debug('destroy_net ' + self.name)
        subprocess.call(["sudo", "ifconfig", "LAN1", "up"])
        subprocess.call(["sudo", "ifconfig", "LAN2", "up"])
        subprocess.call(["sudo", "ovs-vsctl", "del-br", "LAN1"])
        subprocess.call(["sudo", "ovs-vsctl", "del-br", "LAN2"])
        log.debug(self.name + ' destroyed')
