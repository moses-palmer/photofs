#!/usr/bin/env python
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

from ._image import Image
from ._util import make_unique


class Tag(dict):
    """A tag applied to an image or a video.

    An image or video may have several tags applied. In that case an image with
    the same location will be present in the image collection of several tags.
    The image references may not be equal.

    Tags are hierarchial. A tag may have zero or one parent, and any number of
    children. The parent-child relationship is noted in the name of tags: the
    name of a tag will be ``<name of grandparents..>/<name of parent>/<name>``.
    """

    def _make_unique(self, base_name, ext):
        """Creates a unique key in this dict.

        See :func:`make_unique` for more information.

        :param str base_name: The name of the file without extension.

        :param str ext: The file extension. A dot (``'.'``) is not added
            automatically; this must be present in ``ext``.

        :return: a unique key
        :rtype: str
        """
        return make_unique(self, base_name, '%s%s', '%s (%d)%s', ext)

    def __setitem__(self, k, v):
        # Make sure keys are strings and items are images or tags
        if not isinstance(k, str) and not (False
                or isinstance(v, Image)
                or isinstance(v, Tag)):
            raise ValueError('Cannot add %s to Tag',
                str(v))

        super(Tag, self).__setitem__(k, v)

    def __init__(self, name, parent = None):
        """Initialises a named tag.

        :param str name: The name of the tag.

        :param Tag parent: The parent tag. This is used to create the full name
            of the tag. If this is ``None``, a root tag is created, otherwise
            this tag is added to the parent tag.
        """
        super(Tag, self).__init__()
        self._name = name
        self._parent = parent

        # Make sure to add ourselves to the parent tag if specified
        if parent:
            parent.add(self)

        self._has_video = False
        self._has_image = False

    @property
    def name(self):
        """The name of this tag."""
        return self._name

    @property
    def parent(self):
        """The parent of this tag."""
        return self._parent

    @property
    def has_image(self):
        """Whether this tag contains at least one image"""
        return self._has_image

    @property
    def has_video(self):
        """Whether this tag contains at least one video"""
        return self._has_video

    def add(self, item):
        """Adds an image or tag to this tag.

        If a tag is added, it will be stored with the key ``item.name``. If this
        key already has a value, the following action is taken:

        - If the value is a tag, the new tag overwrites it.
        - If the value is an image, a new unique name is generated and the
          image is moved.

        :param item:
            An image or a tag.
        :type item: Image or Tag

        :raises ValueError: if item is not an instance of :class:`Image` or
            :class:`Tag`
        """
        if isinstance(item, Image):
            # Make sure the key name is unique
            key = self._make_unique(item.title, '.' + item.extension)
            self[key] = item

            self._has_image = self._has_image or not item.is_video
            self._has_video = self._has_image or item.is_video

        elif isinstance(item, Tag):
            previous = self.get(item.name)
            self[item.name] = item

            # Re-add the previous item if it was an image
            if isinstance(previous, Image):
                self.add(previous)

            self._has_image = self._has_image or item.has_video
            self._has_video = self._has_image or item.has_image

        else:
            raise ValueError('Cannot add %s to a Tag',
                str(item))
