## Overview

Yum-axelget is a plugin for yum that accelerates download rate with multi-threads by axel. 

Feature:

 - Use axel to download rpm pakcage, as well as delta package(a.k.a drpm or presto)
 - Also download repo metadata based on yum.conf.mdpolicy 
 - Format the output of axel and let it look like default yum progress bar

## Download

You can get the program from https://github.com/crook/yum-axelget/releases

## Installation

Run 'sudo python setup.py install' in source directory.
or:

    sudo cp axelget.conf /etc/yum/pluginconf.d/
    sudo cp axelget.py  /usr/lib/yum-plugins/

## Debug

Run "sudo python /usr/bin/yum --debuglevel=3 YumCommand"

Please send the console output of the above command for help and support

## Contribution

- Get code from https://github.com/crook/yum-axelget
- Change and test in your localhost
- Send pull request to https://github.com/crook/yum-axelget
- You can also help to review patches in https://github.com/crook/yum-axelget/pulls

## Help&Support

Please report your problem by create a new issue in github:
https://github.com/crook/yum-axelget/issues

Or send email to Ray Chen <chenrano2002@gmail.com>

Or visit this website for help
http://yum-axelget.googlecode.com/


