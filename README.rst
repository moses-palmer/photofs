photofs
=======

*photofs* is an application that allows you to mount the tags in the photo
database from `Shotwell <https://wiki.gnome.org/Apps/Shotwell>`_ as directories
in a virtual file system.


Usage
-----

To add directories for all tags under ``$PHOTOFS_PATH``, run the following
command::

    photofs $PHOTOFS_PATH

After this, ``$PHOTOFS_PATH/Photos`` will contain directories for all photo
tags, and ``$PHOTOFS_PATH/Videos`` will contain directories for all video tags.

Run ``photofs --help`` for a list of all command line arguments.


How do I change the names of photos and videos?
-----------------------------------------------

*photofs* will use the title of an image as file name. If the image does not
have a title, the exposure time will be used. If more than one image is shot at
the same time, the file names will be made unique by appending *(1)*, *(2)* etc.
to the file name.

Run ``photofs --help`` to see how to change the time format used.
