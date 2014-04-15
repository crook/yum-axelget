# Author: Ray Chen <chenrano2002@gmail.com>
#
# heavily modified from axelget.py created by
#         Wesley Wang <cnwesleywang@gmail.com>
# 
# @ Description:
#   A plugin for the Yellowdog Updater Modified which enables YUM use
#   multiple threads utility 'axel' to download packages.
#
# @ Installation:
#   You could download it from:
#   http://code.google.com/p/yum-axelget/downloads/list
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import os, sys, time, datetime, glob
import os.path
import threading
import yum
from yum import misc
from yum.drpm import DeltaInfo, DeltaPackage
from yum.plugins import PluginYumExit, TYPE_CORE, TYPE_INTERACTIVE
from urlgrabber.progress import TextMeter

requires_api_version = '2.3'
plugin_type = (TYPE_CORE,)

enablesize=300000
trymirrornum=-1
maxconn=5
httpdownloadonly=False
cleanOnException=0

class Axel(threading.Thread):
    """A thread to do axel download work"""

    COMMAND = 'axel'

    def __init__(self, debug=False, **kwargs):
        threading.Thread.__init__(self)
        self.debug  = debug
        self.remote = kwargs.get('remote', '')
        self.local  = kwargs.get('local', '')
        self.conn   = kwargs.get('conn', None)
        threading.Thread.__init__(self)

        self.__return = None
        self._init_cmd()

    def _init_cmd(self):

        opt = "-q " # quite mode
        if self.debug:
            opt = "-a "
        # specify an alternative number of connections here.
        if self.conn:
            opt += "-n %s"%self.conn
        self.cmd = "axel %s %s -o %s" %(opt, self.remote, self.local)

    def stop(self):
        self._Thread__stop()

    def run(self):
        self.__return = os.system(self.cmd)

    @property
    def output(self):
        return self.__return


def is_plugin_exists(name):
    """
    Check whether a plugin is installed.
    """
    try:
        name = __import__(name)
    except ImportError, e:
        print "(Failed to load module %s: %s)" % (name , e)
        return False
    return name


def exec_axel(conduit, remote, local, size, conn=None, text=None):
    """ Run axel binary to download"""

    if not size or size == -1:
        # we need size here. if not, we do nothing
        conduit.info(3, "axel got unknow size")
        return

    # new thread to run axel
    conf = conduit.getConf()
    axel_debug = False
    if conf.debuglevel >=3:
        axel_debug = True
    axel = Axel(debug=axel_debug,remote=remote,local=local,conn=conn)
    axel.start()

    # make axel outout look like yum output
    tm = TextMeter()
    size = int(size)
    filename = os.path.basename(local)
    if not text:
        text = filename
    # compose text console output
    tm.start(filename=filename, size=size,text=str(text))

    lastSize = curSize = 0
    slow_count = 0
    while True:

        live = axel.isAlive()
        if curSize >= size or not live:
            if live:
                conduit.info(3, "axel is still alive")
            break

        try:
            curSize = os.path.getsize(local)
        except OSError, e:
            # maybe axel still don't generate local file
            # just continue to the following time call
            curSize = 0
            pass

        # update the text bar every one second
        tm.update(curSize)
        time.sleep(0.5)

        # too slow, Less than 1000 bytes/sec transferred
        # the last 30 second
        if (curSize - lastSize) < 1000:
            slow_count +=1
            if slow_count == 60:
                conduit.info(3, "Operation too slow. Less than 1000 \
bytes/sec transferred the last 30 seconds")
                axel.stop()
                break

        lastSize = curSize
    # end while

    axel.join(timeout=600)
    if axel.output == 0:
        tm.end(size)
    else:
        tm.end(curSize)

    return axel.output

def download_drpm(conduit, pkgs):
    """
    Download delta rpm.
    """
    presto_info = {}
    downloaded_drpm_pkgs = []

    # dummy error handle function
    errors = {}
    def adderror(po, msg):
        errors.setdefault(po, []).append(msg)
        if po.localpath.endswith('.tmp'):
            misc.unlink_f(po.localpath) # won't resume this..

    # Be careful here, 'pkgs' parameter is called by object reference
    # which mean it's mutable
    presto = DeltaInfo(conduit._base, pkgs, adderror)
    if not pkgs:
        conduit.info(3, "Not found any avariable drpm")
        return downloaded_drpm_pkgs

    # See which deltas we need to download; if the delta is already
    # downloaded, we can start it reconstructing in the background
    conduit.info(3, "Start download DRPM using axel")
    for dp in pkgs:

        if not isinstance(dp, DeltaPackage):
            continue

        conduit.info(3, "Download %s using axel" %str(dp))
        # localpath is like this:
        #  /var/cache/yum/x86_64/20/updates/packages/bash-4.2.45-4.fc20_4.2.46-4.fc20.x86_64.drpm
        deltapath = dp.localPkg()

        # skip the size is less then ena
        totsize = long(dp.size)
        if totsize <= enablesize:
            conduit.info(3, "skip %s since its size(%s) lesss then enablesize(%s)" %(str(dp),totsize, enablesize))
            downloaded_drpm_pkgs.append((dp, False))
            continue


        fastest = get_fastest_mirror(dp.repo.urls)
        # relativepath format is like 'drpms/package-name.fc12.i686.drpm'
        remoteURL = os.path.join(fastest, dp.relativepath)

        result = False
        if not os.path.exists(deltapath):
            result = exec_axel(conduit, remoteURL, deltapath, totsize)

        #if dp.verifyLocalPkg():
            #presto.rebuild(dp)

        success = result == 0 or dp.verifyLocalPkg()
        # no matter with success or failure, we need mark DRPM there
        # so later yum core will still download the DRPM other than
        # use axel to full rpm package
        downloaded_drpm_pkgs.append((dp,success))

    return downloaded_drpm_pkgs

def get_fastest_mirror(mirrors):
    # If yum-fastestmirror is not found, assume the first url
    # is fastest! FIXME!
    fastestmirror = is_plugin_exists("fastestmirror")
    if not fastestmirror:
        return mirrors[0]

    # Returns the sorted list of mirrors according to the 
    # increasing response time of the mirrors
    sorted_list = fastestmirror.FastestMirror(mirrors).get_mirrorlist()
    return sorted_list[0]

def get_metadata_list(repo, repomd, localFlag):
        """Parser repomd.xml file and return metadata url list"""
        # Load metadata file
        # http://createrepo.baseurl.org/wiki
        metadata_list = []

        try:
            md = yum.repoMDObject.RepoMD(repo.id, repomd)
            #md.dump()
        except yum.Errors.RepoMDError, e:
            #print "load %s failed:%s" %(repomd, str(e))
            # load repmod file error, break
            return metadata_list

        # choose what metadata need to download based on mdpolicy
        #mdtypes = repo._mdpolicy2mdtypes()
        mdtypes = []
        all_mdtypes = ['group', 'filelists', 'group_gz', 'primary', "pkgtags",
                       'primary_db', 'other_db', 'other', "prestodelta"
                       'filelists_db', 'updateinfo']

        # repo.mdpolicy is ["group:small"]
        mdpolicy = "".join(repo.mdpolicy)
        if mdpolicy in ["instant", "group:all"]:
            mdtypes.extend(all_mdtypes)
        if mdpolicy in ["group:main"]:
            mdtypes.extend(["primary", "primary_db", "filelists", "group","prestodelta",
                            "filelist_db", "group_gz", "updateinfo", "pkgtags"])
        if mdpolicy in ["group:small"]:
            mdtypes.extend(["primary", "primary_db", "group",
                            "group_gz", "updateinfo", "pkgtags"])
        if mdpolicy in ["group:primary"]:
            mdtypes.extend(["primary", "primary_db"])

        mdtypes.append('prestodelta')

        # parser metadata file
        for ft in md.fileTypes():

            if ft not in mdtypes:
                #print "%s is not in mdtypes"%ft
                continue

            try:
                repoData = md.getData(ft)
            except yum.Errors.RepoMDError:
                #print "requested datatype %s not available" % ft
                pass
            else:
                (type, location) = repoData.location
                filename = os.path.basename(location)
                # some data don't have size, like pkgtags
                size = repoData.size
                if not size:
                    size = -1
                local_filename = os.path.join(repo.cachedir, filename)

                if localFlag: 
                    tuple = (ft, local_filename,int(size))
                    metadata_list.append(tuple)
                else:
                    tuple = (ft, location,int(size))
                    metadata_list.append(tuple)

        return metadata_list

def init_hook(conduit):
    global enablesize,trymirrornum,maxconn,cleanOnException,httpdownloadonly
    global maxhostfileage
    enablesize = conduit.confInt('main','enablesize',default=300000)
    trymirrornum = conduit.confInt('main','trymirrornum',default=-1)
    maxconn = conduit.confInt('main','maxconn',default=5)
    httpdownloadonly=conduit.confBool('main','onlyhttp',default=False)
    cleanOnException=conduit.confInt('main','cleanOnException',default=0)
    return

def prereposetup_hook(conduit):
    conduit.info(3, 'pre repo setup')

    repos = conduit.getRepos()
    conf = conduit.getConf()

    global httpdownloadonly, maxconn
    for repo in repos.listEnabled():
        #print repo.dump()

        # need to get fastest mirror!
        mirrors = repo.urls
        fastest = mirrors[0]

        localMDFile = os.path.join(repo.cachedir, 'repomd.xml')

        need_download_mdFile = True
        if os.path.exists(localMDFile):
            if repo.metadataCurrent():
                # if md file is smaller than maxhostfileage, 
                # don't need update it!
                need_download_mdFile = False

        if need_download_mdFile:
            # get fastest mirror
            fastest = get_fastest_mirror(mirrors)
            if fastest.startswith("file://"):
                conduit.info(3, "Skip local site: %s" % fastest)
                continue

            if fastest.startswith("ftp://") and httpdownloadonly:
                conduit.info(3, "Skip ftp site: %s" %fastest)
                continue

            conduit.info(3, "%s use fastest mirror: %s" %(repo.id, fastest))

            if os.path.exists(localMDFile):
                # remove metadata download last time
                for (mdtype, filename, size) in get_metadata_list(repo, localMDFile, True):
                    if os.path.exists(filename):
                        os.unlink(filename)
    
                    if mdtype.endswith("_db"):
                        local = filename.replace('.bz2', '')
                        if os.path.exists(local):
                            os.unlink(local)

                # now remove local md file
                os.unlink(localMDFile)

            # use single thread to download repomd.xml
            try:
                repo._getFile(relative=repo.repoMDFile, local=localMDFile)
            except:
                continue
            # update time stampe
            os.utime(localMDFile, None)
        else:
            # repomd.xml is not update, so move to next repo
            conduit.info(2, "No metadata available for %s" % repo.id)
            continue

        # get latest repomd file
        # repo.repoXML

        # load metadata file
        for (mdtype, remote, size) in get_metadata_list(repo, localMDFile, False):

            filename = os.path.basename(remote)
            remoteURL = os.path.join(fastest, remote)
            localFile = os.path.join(repo.cachedir, filename)
            if size < enablesize:
                conduit.info(3, "skip %s since its size(%s) lesss then enablesize(%s)" %(filename, size, enablesize))
                continue
            
            dbFile = localFile
            if mdtype.endswith("_db"):
                dbFile = localFile.replace('.bz2', '')

            if (not os.path.exists(localFile)) and (not os.path.exists(dbFile)):

                text = "%s/%s" %(repo.id, mdtype)
                exec_axel(conduit, remoteURL, localFile, size, text=text)
            
        conduit.info(2, "update %s metadata successfully" %repo.id)

    conduit.info(3, "Finish Download MetaData of Enabled Repo")

def predownload_hook(conduit):

    global enablesize,cleanOnException,httpdownloadonly
    preffermirror=""
    PkgIdx=0
    drpm_name=""

    pkgs = conduit.getDownloadPackages()

    # NOTE: here we must make copy of pkgs, since the following download_drpm
    # will modify the input parameter 'pkglist'. That will eventually leads to
    # unexpectedly modify conduit._pkglist which will be used later in yum main
    # workflow code. Don't remove this copy
    pkglist = []
    for po in pkgs:
        pkglist.append(po)

    # Download drpm
    downloaded_drpm_pkgs = download_drpm(conduit, pkglist)

    TotalPkg=len(pkgs)
    for po in pkgs:
        PkgIdx+=1

        # Skip drpms which has been process.
        checked_drpm_flag = False
        for (deltaPackage, success) in downloaded_drpm_pkgs:
            # Print deltaInfo['filename']
            if po.name == deltaPackage.name:
                if success:
                    conduit.info(3, "success to download %s drpm, skip full rpm" % po.name)
                else:
                    conduit.info(3, "fail to download %s drpm, yum core will continue" %po.name)

                # DRPM have been process
                drpm_name = os.path.basename(deltaPackage.localpath)
                checked_drpm_flag = True
                break
        # end for

        if checked_drpm_flag:
            conduit.info(3, "(%d/%d): %s has drpm for package %s, skip full rpm download" %
                                                      (PkgIdx, TotalPkg, drpm_name, po.name))
            continue

        if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
            continue
        totsize = long(po.size)
        ret = False

        if totsize <= enablesize:
            conduit.info(3, "(%d/%d): Size of %s package in %s repo is less than enablesize %d bytes,Skip multi-thread!" %
                                                      (PkgIdx, TotalPkg, po.name, po.repo.id, enablesize))
            continue
        else:
            conduit.info(3, "(%d/%d): Ok, try to use axel to download the following big file: %d bytes" %(PkgIdx, TotalPkg, totsize))
    
        # Get local pkg info
        local = po.localPkg()

        # If this pkg is found in cache directory and size is ok,
        # just skip it, go to next pkg
        if os.path.exists(local) and not os.path.exists(local + ".st"):
            if totsize == os.stat(local).st_size:
                conduit.info(3,"Package already exists in cache dir,skip it!")
                continue

        # Remove incomplete pkg
        localall = "%s %s" % (local,local+".st")
        rmcmd = "rm -f %s" % (localall)

        curmirroridx = 0
        conduit.info(3,"Cleaning all key files")
        os.system(rmcmd)

        # calculate number of connections
        connnum = totsize / enablesize
        if connnum*enablesize<totsize:
            connnum+=1
        if connnum > maxconn:
            connnum = maxconn

        mirrors=[]
        mirrors[:0]=po.repo.urls
        if preffermirror != "":
            mirrors[:0] = [preffermirror]
        for url in mirrors:
            if url.startswith("ftp://") and httpdownloadonly:
                print "Skip Ftp Site:",url
                continue
            if url.startswith("file://"):
                print "Skip Local Site:",url
                continue

            curmirroridx += 1
            if (curmirroridx > trymirrornum) and (trymirrornum != -1):
                conduit.info(2, "Package %s has tried %d mirrors,Skip plugin!" %
                                                      (po.repo.id,trymirrornum))
                break

            remoteurl =  os.path.join(url, po.remote_path)
            exec_axel(conduit,remoteurl,local,totsize,connnum)
            time.sleep(1)

            if os.path.exists(local+".st"):
                conduit.info(3,"axel exit by exception, try another mirror")
                if cleanOnException:
                    conduit.info(3,"Because cleanOnException enabled, "
                                              "remove key files first")
                    os.system(rmcmd)
                continue

            #this mirror may not update yet
            elif not os.path.exists(local): 
                continue
            else:
                ret = True
                preffermirror=url
                break
        if not ret:
            conduit.info (3,"Try to run rm cmd:%s"  % rmcmd)
            os.system(rmcmd)


if __name__ == "__main__":
    mirrors = ['http://ftp.riken.jp/Linux/fedora/releases/20/Everything/i386/os/',
               'http://kambing.ui.edu/fedora/releases/20/Everything/i386/os/',
               'http://mirrors.163.com/fedora/releases/20/Everything/i386/os/',
               'http://mirrors.sohu.com/fedora/releases/20/Everything/i386/os/',
               'http://ftp.nchu.edu.tw/Linux/fedora/releases/20/Everything/i386/os/']

    sys.path.append('/usr/lib/yum-plugins')
    print get_fastest_mirror(mirrors)

    # test update repo
    yb = yum.YumBase()
    up_repo = yb.repos.findRepos('updates')[0]
    remd_file = os.path.join(up_repo.cachedir, 'repomd.xml')
    print "updates repo metadata: ", get_metadata_list(up_repo, remd_file, True)
    print "updates repo metadata: ", get_metadata_list(up_repo, remd_file, False)

    fedora_repo = yb.repos.findRepos('fedora')[0]
    fedora_file = os.path.join(fedora_repo.cachedir, 'repomd.xml')
    print "fedora repo metadata: ",get_metadata_list(fedora_repo, fedora_file, True)
    print "fedora repo metadata: ",get_metadata_list(fedora_repo, fedora_file, False)
