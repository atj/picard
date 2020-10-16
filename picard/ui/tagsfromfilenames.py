# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2006-2007 Lukáš Lalinský
# Copyright (C) 2009, 2014, 2019-2020 Philipp Wolfer
# Copyright (C) 2012-2013 Michael Wiencek
# Copyright (C) 2014, 2017 Sophist-UK
# Copyright (C) 2016-2017 Sambhav Kothari
# Copyright (C) 2017 Ville Skyttä
# Copyright (C) 2018 Laurent Monin
# Copyright (C) 2018 Vishal Choudhary
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from collections import OrderedDict
import os.path
import re

from PyQt5 import QtWidgets

from picard import config
from picard.util.tags import display_tag_name

from picard.ui import PicardDialog
from picard.ui.ui_tagsfromfilenames import Ui_TagsFromFileNamesDialog
from picard.ui.util import StandardButton


class TagMatchExpression:
    _numeric_tags = ('tracknumber', 'totaltracks', 'discnumber', 'totaldiscs')

    def __init__(self, expression, replace_underscores=False):
        self.replace_underscores = replace_underscores
        self._tag_re = re.compile(r"(%\w+%)")
        self._parse(expression)

    def _parse(self, expression):
        self._group_map = {}
        format_re = ['(?:^|/)']
        for i, part in enumerate(self._tag_re.split(expression)):
            if part.startswith('%') and part.endswith('%'):
                tag = part[1:-1]
                group = '%s_%i' % (tag, i)
                self._group_map[group] = tag
                if tag in self._numeric_tags:
                    format_re.append(r'(?P<' + group + r'>\d+)')
                elif tag == 'date':
                    format_re.append(r'(?P<' + group + r'>\d+(?:-\d+(?:-\d+)?)?)')
                else:
                    format_re.append(r'(?P<' + group + r'>[^/]*?)')
            else:
                format_re.append(re.escape(part))
        # Optional extension
        format_re.append(r'(?:\.\w+)?$')
        self._format_re = re.compile("".join(format_re))

    @property
    def matched_tags(self):
        # Return unique values, but preserve order
        return list(OrderedDict.fromkeys(self._group_map.values()))

    def match_file(self, filename):
        match = self._format_re.search(filename.replace('\\', '/'))
        if match:
            result = {}
            for group, value in match.groupdict().items():
                value = value.strip()
                tag = self._group_map[group]
                if tag in self._numeric_tags:
                    value = value.lstrip("0")
                if self.replace_underscores:
                    value = value.replace('_', ' ')
                result[tag] = value
            return result
        else:
            return {}


class TagsFromFileNamesDialog(PicardDialog):

    autorestore = False

    options = [
        config.TextOption("persist", "tags_from_filenames_format", ""),
    ]

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.ui = Ui_TagsFromFileNamesDialog()
        self.ui.setupUi(self)
        self.restore_geometry()
        items = [
            "%artist%/%album%/%title%",
            "%artist%/%album%/%tracknumber% %title%",
            "%artist%/%album%/%tracknumber% - %title%",
            "%artist%/%album% - %tracknumber% - %title%",
            "%artist% - %album%/%title%",
            "%artist% - %album%/%tracknumber% %title%",
            "%artist% - %album%/%tracknumber% - %title%",
        ]
        tff_format = config.persist["tags_from_filenames_format"]
        if tff_format not in items:
            selected_index = 0
            if tff_format:
                items.insert(0, tff_format)
        else:
            selected_index = items.index(tff_format)
        self.ui.format.addItems(items)
        self.ui.format.setCurrentIndex(selected_index)
        self.ui.buttonbox.addButton(StandardButton(StandardButton.OK), QtWidgets.QDialogButtonBox.AcceptRole)
        self.ui.buttonbox.addButton(StandardButton(StandardButton.CANCEL), QtWidgets.QDialogButtonBox.RejectRole)
        self.ui.buttonbox.accepted.connect(self.accept)
        self.ui.buttonbox.rejected.connect(self.reject)
        self.ui.preview.clicked.connect(self.preview)
        self.ui.files.setHeaderLabels([_("File Name")])
        self.files = files
        self.items = []
        for file in files:
            item = QtWidgets.QTreeWidgetItem(self.ui.files)
            item.setText(0, os.path.basename(file.filename))
            self.items.append(item)

    def preview(self):
        expression = TagMatchExpression(self.ui.format.currentText(), self.ui.replace_underscores.isChecked())
        columns = expression.matched_tags
        headers = [_("File Name")] + list(map(display_tag_name, columns))
        self.ui.files.setColumnCount(len(headers))
        self.ui.files.setHeaderLabels(headers)
        for item, file in zip(self.items, self.files):
            matches = expression.match_file(file.filename)
            for i, column in enumerate(columns):
                item.setText(i + 1, matches.get(column, ''))
        self.ui.files.header().resizeSections(QtWidgets.QHeaderView.ResizeToContents)
        self.ui.files.header().setStretchLastSection(True)

    def accept(self):
        expression = TagMatchExpression(self.ui.format.currentText(), self.ui.replace_underscores.isChecked())
        for file in self.files:
            metadata = expression.match_file(file.filename)
            for name, value in metadata.items():
                file.metadata[name] = value
            file.update()
        config.persist["tags_from_filenames_format"] = self.ui.format.currentText()
        super().accept()
