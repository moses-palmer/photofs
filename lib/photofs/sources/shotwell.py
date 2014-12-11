# coding: utf-8
# photofs
# Copyright (C) 2012-2014 Moses Palmér
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.

import os

from xdg.BaseDirectory import xdg_data_dirs

from .. import *


# Try to import sqlite
try:
    import sqlite3
except ImportError:
    sqlite = None


@ImageSource.register('shotwell')
class ShotwellSource(FileBasedImageSource):
    """Loads images and videos from Shotwell.
    """
    def __init__(self, *args, **kwargs):
        if sqlite3 is None:
            raise RuntimeError('This program requires sqlite3')
        super(ShotwellSource, self).__init__(*args, **kwargs)

    @property
    def default_location(self):
        """Determines the location of the *Shotwell* database.

        :return: the location of the database, or ``None`` if it cannot be
            located
        :rtype: str or None
        """
        for d in xdg_data_dirs:
            result = os.path.join(d, 'shotwell', 'data', 'photo.db')
            if os.access(result, os.R_OK):
                return result

    def load_tags(self):
        db = sqlite3.connect(self._path)
        try:
            # The descriptions of the different image tables; the value tuple is
            # the header of the ID in the tag table, the map of IDs to images
            # and whether the table contains videos
            db_tables = {
                'phototable': ('thumb', {}, False),
                'videotable': ('video-', {}, True)}

            # Load the images
            for table_name, (header, images, is_video) in db_tables.items():
                results = db.execute("""
                    SELECT id, filename, exposure_time, title
                        FROM %s""" % table_name)
                for r_id, r_filename, r_exposure_time, r_title in results:
                    images[r_id] = FileBasedImage(
                        r_title,
                        r_filename,
                        r_exposure_time,
                        is_video)

            # Load the tags
            results = db.execute("""
                SELECT name, photo_id_list
                    FROM tagtable
                    ORDER BY name""")
            for r_name, r_photo_id_list in results:
                # Ignore unused tags
                if not r_photo_id_list:
                    continue

                # Hierachial tag names start with '/'
                path = r_name.split('/') if r_name[0] == '/' else ['', r_name]
                path_name = os.path.sep.join(path)

                # Make sure that the tag and all its parents exist
                tag = self._make_tags(path_name)

                # The IDs are all in the text of photo_id_list, separated by
                # commas; there is an extra comma at the end
                ids = r_photo_id_list.split(',')[:-1]

                # Iterate over all image IDs and move them to this tag
                for i in ids:
                    if i[0].isdigit():
                        # If the first character is a digit, this is a legacy
                        # source ID and an ID in the photo table
                        image = db_tables['phototable'][1].get(int(i))
                    else:
                        # Iterate over all database tables and locate the image
                        # instance for the current ID
                        image = None
                        for table_name, (header, images, is_video) \
                                in db_tables.items():
                            if not i.startswith(header):
                                continue
                            image = images.get(int(i[len(header):], 16))
                            break

                    # Verify that the tag only references existing images
                    if image is None:
                        continue

                    # Remove the image from the parent tags
                    parent = tag.parent
                    while parent:
                        for k, v in parent.items():
                            if v == image:
                                del parent[k]
                        parent = parent.parent

                    # Finally add the image to this tag
                    tag.add(image)

        finally:
            db.close()
