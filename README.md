rhythmbox-android-remote v0.2
================

Allow to remote control Rhythmbox v3 or later with Banshee remote application 
from Nikitas Stamatopoulos:

https://play.google.com/store/apps/details?id=org.nstamato.bansheeremote&hl=es

-----------

*How it works:*

 - Enable the plugin in Edit > Plugins
 - Launch banshee remote in Android phone
 - Connect to the computer IP where RB is working, using port 8484.
 - Control it!

*How to install:*

For debian & debian-based distros:

    sudo apt-get install python-sqlite git

Then install the plugin:

<pre>
rm -rf ~/.local/share/rhythmbox/plugins/rhythmbox-android-remote
cd ~/.local/share/rhythmbox/plugins/
git clone https://github.com/fossfreedom/rhythmbox-android-remote
</pre>

For Ubuntu 14.04 and later:

It's available in my rhythmbox-plugins PPA. Installation instructions in this AskUbuntu Q&A:

http://askubuntu.com/questions/147942/how-do-i-install-third-party-rhythmbox-plugins

-------

*Authors:*

The original author of this plugin is Pedro M. Baeza <pedro.baeza@gmail.com>. Based on an script from 
Baptiste Saleil:
https://github.com/bsaleil/rhythmbox-android-remote

Current fork for Rhythmbox 3.0 - fossfreedom <foss.freedom@gmail.com>


-------

Licenses:

This plugin code is released under the GPL3+ license.
