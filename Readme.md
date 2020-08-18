# Morphoblend

**Morphoblend** is an add-on for `Blender` for the import, processing, editing, quantification, rendering and export of cellular meshes derived from light microscopy data.

**MorphoBlend** has been designed as a companion to **PlantSeg** (see PlantSeg on [GitHub](https://github.com/hci-unihd/plant-seg) and the [publication](https://elifesciences.org/articles/57613)) a tool for cell instance  segmentation in densely packed 3D volumetric images of plant tissues. Together with **seg2mesh** (see seg2mesh on [GitHub](https://github.com/lorenzocerrone/python-seg2mesh)), it alows to visualise, process, edit and quantify cells in tissues:

![The MorphoBlend AddOn](Images/Morphoblend_Banner.png)

**MorphoBlend** can also be used for cell meshes generated by other modalities.

## Features

- `Blender` add on.
- Import cell meshes in `PLY` format.
- Can efficiently handle thousands of cells.
- Built in tools for processing (coloring, renaming, filtering, sorting).
- Merging and splitting of cells.
- Quantification, visualisation and export of cell attributes (volume, area, ...).
- ... more to come :-).

## Requirements

- `Blender`: [download](www.blender.org) v2.8 or higher.
- A basic understanding of how Blender is working. See [this series of videos to get started](https://www.youtube.com/playlist?list=PLa1F2ddGya_-UvuAqHAksYnB0qL9yWDO6).

## Installation

**MorphoBlend** installs as any other `Blender` addon.

- Download **Morphoblend** as a `zip` file.

![](Images/dl_zip.png)

- Open `Blender`.
- Install the addon as [described here](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html).

## Gallery

![Gallery](Images/LR_1.png)
![Gallery](Images/LR_2.png)
![Gallery](Images/Ovule.png)
![Gallery](Images/Ovule2.png)

## Versions

##### v0.3.4 | Filter cells based on volume [2020-08-14]

  Cells which volume is in a given range are selected and listed (as aliases) in a *Filter results* collection. Works on a selection or on *all* cells of the scene (visible or not).

##### v0.3.3 | Bulk color cells in collection [2020-08-12]

 All cells present in a collection matching a given pattern (`regex`-style) can be colored.

##### v0.3.2 | Bug fixes [2020-08-10]

##### v0.3.1 | Bug fixes & improvements [2020-08-07]

Fixed (nasty) bug affecting the volume computation.
Colorize cells according to volume or area.

##### v0.3.0 | Splitting and merging [2020-08-07]

Cells can be split and merged interactively. Cells to be processed can be added/removed from the `Work List` which can be navigated.

##### v0.2.0 | Quantification and visualisation [2020-08-01]

Quantification of cell volumes & area.

##### v0.1.0 | Initial release [2019-12-18]

Import and Process modules implemented.

## Acknowledgments

The following people have actively contributed to the development, improvement or test of **MorphoBlend**:

- Sami Bouziri

## Using MorphoBlend

**MorphoBlend** is available as a tab on the right side of Blender's main 3D viewport.
It consists of several modules:

- Import
- Process
- Edit
- Quantify

![The MorphoBlend AddOn](Images/MorphoBlend.png)

### Import

This module handles import of the cells mesh and their immediate post-processing.

![The MorphoBlend AddOn](Images/Import.png)

**Path:** Type or select (click on `folder` icon) a folder containing the files to import. Only files in  `PLY` format can be imported. The importer will import:

- all files in the folder which end by `.ply`

- all `ply` files contained in sub-folders of the main folder as long as this is named `tXX` (*eg* t03). This allows the automatic import of whole time series.

```python
\Folder:
  |---> file1.ply               <- will be imported
  |---> file2.txt               <- will NOT be imported
  |---> \t00
  |       |---> file3.txt       <- will NOT be imported
  |       |---> file4.ply       <- will be imported
  |       |       (...)
  |       |---> file6.ply       <- will be imported
  |
  |---> \t01
          |---> file7.ply       <- will be imported
          |---> file8.ply       <- will be imported
```

Files located in a subfolder will be automatically placed in a sub-collection of the same name, while all other files will be put in the `Imported` collection.

**Microscope settings:**

- **Magnification**: magnification of the lense used during imaging. [*Currently not used*].

- **Voxel size**: physical dimensions of the voxel in µm. This controls the anisotrpic scaling of the meshes and all calculations (volume, area, dimensions...).

**Post-processing:**

- **Apply rotation**: define the rotation (in degrees) along the X, Y & Z axis apply to all meshes after import. Useful to correct for swaps in the orientation of axis.

- **Finalize smoothing**: whether all cells are remeshed and decimated to keep their aspects correct and reduce the number of triangle. Beware: not ticking this box can result in **large** files.

- **Color cells**:  to assign or not a color at random from the selected **palette**.

**Import:** Pressing this button will start the import process. The bar indicates progress. **(!)** Check *known bug section*.

### Process

This modules handles the selection, colouring, sorting and filtering of the cells.

![The MorphoBlend AddOn](Images/Process.png)

**Assing color:** assign to a selection of cells either a specific color (prefix `[C]`) or a color at random in a palette (prefix `[P]`). In the latter case, pressing `Colorize` several times shuffle the color assignment, which is interesting when neighbouring cells have similar colors.

**Bulk color cells in collection:** all cells of a collection matching a given pattern (`regex`-style) are assigned a specific color or colored randomely from the chosen palette.

**Finalize modifiers:** will "burn" any mesh modifier (*eg* remesh,  decimate) applied to the selected cells. This can be a way to reduce numer of triangles (and file size), if the meshes were imported without finalizing the smoothing (see *Import*).

**Rename:** will rename all selected objects. `regex`-style expression can be used in the search and replace fields.

**Group into collection:** will move all objects which name fit the `regex`-style expression, to a collection of the same name.

**Filter on volume:** Cells which volume is in a given range are selected and listed (as *aliases*) in a *Filter results* collection. When `Apply filter to all` is ticked,  the filtering is applied to *all* cells of the scene (visible or not, selected or not).

### Edit

This module handles the modification of the cell meshes.

![The MorphoBlend AddOn](Images/Edit.png)

There are keyboard shortcuts to call the functions; hover the mouse over the button to reveal them.

**Work List:** The work list is a special collection that stores references to cells that need to be merged or split. Selected cells can be added/removed by pressing the corresponding buttons. Navigate in the list with the next/previous buttons. Important: cells in the Work List are *aliases* (or links) of the original cells, that remain in their original collection. Removing a cell from the working list does not remove it from its collection nor erase it.

**Merge:** This merges two or more selected contiguous cells in a single mesh.

![https://youtu.be/mK8IlsS0CT0](Images/Merge_vid.png)

[Link to video](https://youtu.be/mK8IlsS0CT0)

**Split:** This splits a single cell. This is a two steps, semi automatic process:

- **Phase 1 - Cutting the cells**:
    1. Press the `Start split` button this will activate the mesh edit mode  **just for the cell to split**. No need to worry about the other cells around, they can't be edited.
    2. Using the `KNIFE` or `BISECT` tools (located on the left tool bar), delineated a plan (`BISECT` tool) or a path (`KNIFE` tool) on the mesh along which the cells will be cut. 
    3. Press `ENTER`
    4. Press `V` to rip the mesh apart. Do ***not*** touch the mouse, use the keybaord arrows to move the cut a little (3-4 keystrokes are sufficient).
    5. Press `ENTER`.


- **Phase 2 - Finalise the split** Press the `Finish Split`. The split cells will be separated in two new cells and their names updated.

**Demos:**

Spliting with `BISECT`

![https://youtu.be/IbCE5WAFq94](Images/Split_Bisect_vid.png)

[Link to video](https://youtu.be/IbCE5WAFq94)

Spliting with `KNIFE`

![https://youtu.be/cxdl3-XK8Rg](Images/Split_Knif_vid.png)

[Link to video](https://youtu.be/cxdl3-XK8Rg)

### Quantify

This module handles all quantifications on cells.

![The MorphoBlend AddOn](Images/Quantify.png)

**Morphometrics:** this computes several metrics on the selected cells. The results are displayed in a table, that can be searched, sorted, cleared and saved to disk as `.CSV` file. For the latter, type or set the path to the output file by pressing the  folder icon.
The output file will contain in addition to the name of the cell and the collections in belongs to, the following metrics:

- Volume (in µm3)
- Area of (in µm2)
- Dimensions along the *X*, *Y* and *Z* axis
- Coordinates of center (*X, Y, Z*)

**Colorize metric:** the selected cells will be coloured according to their *Volume* or *Area*, using the full range of the selected palette. A lookup table is displayed.

![The MorphoBlend AddOn](Images/Colorize_Quantify.png)

### Render

Not yet implemented.

### Export

Not yet implemented.

## Known bugs

**Import**: The very first import after (re)starting Blender usually skips the first file. Erasing the cells, and repeating the import solves the issue.

**Quantify: colorize metric**: the lookup table remains in the 3D viewport until `Blender` is quit & relaunched.
