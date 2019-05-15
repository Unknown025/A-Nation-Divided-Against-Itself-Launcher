import logging
import threading
from urllib.request import urlretrieve
from zipfile import ZipFile, BadZipfile
import os
import json
import time
import sys
import subprocess

LOG_FILENAME = "launcher.log"
FORMAT = '[%(asctime)s %(levelname)s]: %(message)s'
logging.basicConfig(filename=LOG_FILENAME, format=FORMAT, level=0)
DownloadedFiles = 0
FailedFiles = 0


def mkdir(dirname):
    if currentOS != "windows":
        os.system("mkdir -p " + dirname)
    else:
        # Windows
        # os.system("MD " + dirname.replace("/", "\\") + " 2>NUL")
        subprocess.call("md " + dirname.replace("/", "\\") + " 2>NUL", shell=True)


currentOS = None
if sys.platform.startswith("win"):
    currentOS = "windows"
    logging.info("Current OS: Windows")
elif sys.platform == "darwin":
    currentOS = "mac"
    logging.info("Current OS: macOS")
else:
    currentOS = "linux"
    logging.info("Current OS: Linux")

bits = "32"
if sys.maxsize > 2**32:
    bits = "64"


class Profile:
    def __init__(self, version):
        # tk.Tk.__init__(self)
        # self.download=Toplevel(root)
        # self.download.grab_set()
        # self.progress=ttk.Progressbar(download, orient=horizontal, length=200, mode='determinate')
        # self.progress.pack()
        self.version = version
        self.libs = []
        self.fileIndex = [("mcdata/versions/%s/%s.json" % (self.version, self.version),
                           "http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.json" % (
                           self.version, self.version)),

                          ("mcdata/versions/%s/%s.jar" % (self.version, self.version),
                           "http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.jar" % (
                           self.version, self.version))
                          ]

        # Load version info
        f = None
        try:
            f = open("mcdata/versions/%s/%s.json" % (self.version, self.version), "rb")
            logging.info("Downloaded version info.")
        except IOError:
            mkdir("mcdata/versions/%s" % self.version)
            self.cdownload1 = threading.Thread(target=self.downloadFile,
                                               args=("mcdata/versions/%s/%s.json" % (self.version, self.version),
                                                     "http://s3.amazonaws.com/Minecraft.Download/versions/%s/%s.json" % (
                                                     self.version, self.version))
                                               )
            self.cdownload1.start()
            self.cdownload1.join()
            f = open("mcdata/versions/%s/%s.json" % (self.version, self.version), "rb")
        sdata = f.read()
        f.close()

        self.versionInfo = json.loads(sdata)
        self.mainClass = self.versionInfo["mainClass"]
        self.mcargs = self.versionInfo["minecraftArguments"]
        self.jar = "versions/%s/%s.jar" % (self.version, self.version)
        for libinfo in self.versionInfo["libraries"]:
            librep = libinfo.get("url", "https://libraries.minecraft.net/")
            name = libinfo["name"]
            package, name, version = name.split(":")
            relpath = package.replace(".", "/") + "/" + name + "/" + version + "/" + name + "-" + version + ".jar"
            self.fileIndex.append(("mcdata/libraries/" + relpath, librep + relpath))
            self.libs.append("libraries/" + relpath)

            if "natives" in libinfo:
                if currentOS in libinfo["natives"]:
                    mkdir("mcdata/natives")
                    natstr = libinfo["natives"][currentOS].replace("${arch}", bits)
                    relpath = package.replace(".",
                                              "/") + "/" + name + "/" + version + "/" + name + "-" + version + "-" + natstr + ".jar"
                    libpath = "mcdata/libraries/" + relpath
                    liburl = librep + relpath
                    if not os.path.exists(libpath):
                        self.cdownload2 = threading.Thread(target=self.downloadFile, args=(libpath, liburl))
                        self.cdownload2.start()
                        self.cdownload2.join()
                        print(">Extract " + libpath)
                        try:
                            zipfile = ZipFile(libpath, "r")
                            for name in zipfile.namelist():
                                if not (name.startswith("META-INF") or name.startswith(".")):
                                    zipfile.extract(name, "mcdata/natives")
                            zipfile.close()
                        except BadZipfile as e:
                            logging.exception(
                                "Zip/Jar file could not be extracted: %s. Error goes as follows: %s" % (name, e))
                            print("[%s WARN]: A faulty zip or jar file was found. This may cause problems!" % (
                                time.strftime("%H:%M:%S")))
                            try:
                                os.remove(libpath)
                            except:
                                pass
                        except:
                            logging.critical("A zip or jar file could not be found. File: %s" % name)
                            "[%s WARN]: Jar file or zip file not found. This may cause errors." % (
                                time.strftime("%H:%M:%S"))

        # We must also get the assets index.
        assetsName = self.versionInfo.get("assets", "legacy")
        assetsIndexFile = "mcdata/assets/indexes/%s.json" % assetsName
        assetsIndexLink = "https://s3.amazonaws.com/Minecraft.Download/indexes/%s.json" % assetsName
        self.cdownload3 = threading.Thread(target=self.downloadFile, args=(assetsIndexFile, assetsIndexLink))
        self.cdownload3.start()
        self.cdownload3.join()
        assetsIndexFile = str(assetsIndexFile)
        f = open(assetsIndexFile, "rb")
        assetsData = json.loads(f.read())
        f.close()

        for key, value in assetsData["objects"].items():
            hash = value["hash"]
            pref = hash[:2]
            self.fileIndex.append((
                "mcdata/assets/objects/%s/%s" % (pref, hash),
                "http://resources.download.minecraft.net/%s/%s" % (pref, hash)
            ))

    def downloadFile(self, filename, url):
        global FailedFiles
        global DownloadedFiles
        dirname = filename.rsplit("/", 1)[0]
        mkdir(dirname)
        filename2 = filename + ".tmp"
        if not os.path.isfile(filename):
            try:
                print("[%s INFO]: Downloading: %s, currently only %s failed." % (
                    time.strftime("%H:%M:%S"), filename, FailedFiles))
                logging.info("Downloading %s" % filename)
                urlretrieve(url, filename2)
                os.rename(filename2, filename)
                DownloadedFiles += 1
                print("[%s INFO]: Finished downloading: %s, currently only %s succeeded." % (
                    time.strftime("%H:%M:%S"), filename, DownloadedFiles))
                logging.info("Finished downloading: %s" % filename)
            except IOError as e:
                print("[%s ERR]: File '%s' could not be downloaded." % (time.strftime("%H:%M:%S"), filename))
                FailedFiles += 1
                logging.error("File '%s' was not downloaded. The error goes as follows: %s" % (filename, e))
                sys.exit(1)
            except WindowsError as e:
                time.sleep(10)
                os.rename(filename2, filename)

        # except:
        #     print "[%s ERROR]: An exception has occured and the process cannot continue." % (time.strftime("%H:%M:%S"))
        #     FailedFiles += 1
        sys.exit(0)

    def downloadMissingFiles(self):
        print("[%s INFO]: Started downloading missing files." % (time.strftime("%H:%M:%S")))
        running_downloads = []
        for filename, url in self.fileIndex:
            if not os.path.exists(filename):
                if len(running_downloads) > 49:
                    for f in running_downloads:
                        f.join()
                    running_downloads = []
                downloadmfiles = threading.Thread(target=self.downloadFile, args=(filename, url))
                downloadmfiles.start()
                running_downloads.append(downloadmfiles)
                # self.downloadmfiles.join()
        for f in running_downloads:
            f.join()

    def downloadForge(self):
        print("[%s INFO]: Started downloading mod files." % (time.strftime("%H:%M:%S")))
        logging.info("Started downloading mod files.")
        urlretrieve(
            "http://anationdividedagainstitself-modpack.rhcloud.com/a-nation-divided-against-itself.json",
            "a-nation-divided-against-itself.json")
        urlretrieve(
            "http://files.minecraftforge.net/maven/net/minecraftforge/forge/1.7.10-10.13.4.1614-1.7.10/forge-1.7.10-10.13.4.1614-1.7.10-universal.jar",
            "forge-universal.jar")
        try:
            zipfile = ZipFile("forge-universal.jar", "r")
            for name in zipfile.namelist():
                if not (name.startswith("META-INF") or name.startswith(".")):
                    zipfile.extract(name, "forgeTemp")
            zipfile.close()
            print(os.getcwd())
            zipfile2 = ZipFile("mcdata/versions/1.7.10/1.7.10.jar", "a")
            os.chdir("forgeTemp")
            for i in os.listdir("."):
                path = "forgeTemp\%s" % i
                zipfile2.write(i)
                logging.info("Added file %s to 1.7.10.jar", i)
            os.chdir("..")
        except BadZipfile as e:
            logging.exception("[Forge]: Zip/Jar file could not be extracted: %s. Error goes as follows: %s", name, e)
            print("[%s WARN]: A faulty zip or jar file was found. This may cause problems!" % (
                time.strftime("%H:%M:%S")))
        win = open("a-nation-divided-against-itself.json", "r")
        data = win.read()
        dn = json.loads(data)
        x = 0
        running_downloads = []
        for i in dn["tasks"]:
            if not os.path.isfile(dn["tasks"][x]["to"]):
                filename = "mcdata/" + dn["tasks"][x]["to"]
                url = "http://anationdividedagainstitself-modpack.rhcloud.com/objects/" + dn["tasks"][x]['location']
                downloadForge = threading.Thread(target=self.downloadFile, args=(filename, url))
                downloadForge.start()
                running_downloads.append(downloadForge)
                if len(running_downloads) > 10:
                    for f in running_downloads:
                        f.join()
            x += 1
        print("[INFO]: Ended downloading files. " + str(DownloadedFiles))
        logging.info("Ended download process. Downloaded: %s, Failed: %s", str(DownloadedFiles), str(FailedFiles))

    def launchcmd(self, username="MinecraftPlayer"):
        libs = [self.jar]
        libs.extend(self.libs)
        cp = ":".join(libs)
        if currentOS == "windows":
            # LOL
            cp = ";".join(libs).replace("/", "\\")
        try:
            self.win = open("usernamecache.json", "r")
            self.username = self.win.readline()
            self.auth_uuid = self.win.readline()
            self.auth_access_token = self.win.readline()
            self.username = self.username.rstrip()
            self.auth_uuid = self.auth_uuid.rstrip()
            self.auth_access_token = self.auth_access_token.rstrip()
            print(self.username)
            print(self.auth_uuid)
            print(self.auth_access_token)
        except:
            print("[WARN]: Authentication failed!")
            self.username = "null"
            self.auth_uuid = "null"
            self.auth_access_token = "null"
        args = self.mcargs
        args = "%s --tweakClass cpw.mods.fml.common.launcher.FMLTweaker" % args
        args = args.replace("${auth_player_name}", self.username)
        args = args.replace("${version_name}", self.version)
        args = args.replace("${game_directory}", ".")
        args = args.replace("${game_assets}", "assets")  # Not even used.
        args = args.replace("${assets_root}", "assets")  # Not even used.
        args = args.replace("${auth_uuid}", self.auth_uuid)
        args = args.replace("${auth_access_token}", self.auth_access_token)
        args = args.replace("${assets_index_name}", self.versionInfo.get("assets", "legacy"))
        args = args.replace("${user_properties}", "{}")
        args = args.replace("${user_type}", "mojang")
        print(args)
        return 'java -cp "%s" -Djava.library.path=natives %s %s' % (cp, self.mainClass, args)
