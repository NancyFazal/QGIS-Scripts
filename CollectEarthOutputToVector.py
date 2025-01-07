"""
Model exported as python.
Name : Collect Earth output to vector
Group : LUC Sampling
With QGIS : 33600
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterNumber,
                       QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem,
                       QgsProject,
                       QgsGeometry,
                       QgsPointXY,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsVectorLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingException)
from PyQt5.QtCore import QVariant
from qgis import processing
import csv
import json
import re

class CollectEarthOutputToVector(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    INPUT_COORDINATE = 'EPSG:4326'
    INPUT_PARAM_HELP = {
        "Input file": "Path to the CSV file",
        "Output Projection": "Projection to which the locations are re-projected. Only Projected Coordinate Systems are allowed",
        "Plot size": "Size of square buffer applied to the plots",
        "Output": "Path to the output vector dataset (Shapefile, GeoPackage)"
    }

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CollectEarthOutputToVector()

    def name(self):
        return 'Collect Earth output to vector'

    def displayName(self):
        return self.tr('Collect Earth output to vector')

    def group(self):
        return self.tr('LUC Sampling')

    def groupId(self):
        return 'luc_sampling'

    def shortHelpString(self):
        return """<html><body>
        <p>converts the Collect Earth CSV files to vector datasets </p> 
        <h2>Parameters</h2>
        """ + "\n".join(f'<h3>{k}</h3><p>{v}</p>' for k, v in self.INPUT_PARAM_HELP.items())

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            'input_file',
            'Input file',
            behavior=QgsProcessingParameterFile.File,
            extension='csv',
            defaultValue=None)
        )

        self.addParameter(QgsProcessingParameterCrs(
            'output_projection',
            'Output Projection',
            defaultValue="EPSG:4326"
        )
        )
        self.addParameter(QgsProcessingParameterNumber(
            'plot_size',
            'Plot size',
            defaultValue=10,
            type=QgsProcessingParameterNumber.Double
        )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        desired_coordinate_system = parameters['output_projection']
        if (desired_coordinate_system.isGeographic()):
            raise QgsProcessingException("Output projection parameter only accepts the Projected Coordinate Systems. Geographic Coordinate Systems are not allowed")
        plot_size = parameters['plot_size']

        vl = QgsVectorLayer("Point", "temporary_points", "memory")
        vl.setCrs(desired_coordinate_system)
        pr = vl.dataProvider()
        vl.startEditing()

        fields = QgsFields()
        fields.append(QgsField("Plot_id", QVariant.Int))
        fields.append(QgsField("SRS", QVariant.String))
        fields.append(QgsField("X", QVariant.Double))
        fields.append(QgsField("Y", QVariant.Double))
        fields.append(QgsField("operator", QVariant.String))
        fields.append(QgsField("savedYear", QVariant.Int))
        fields.append(QgsField("savedMonth", QVariant.Int))
        fields.append(QgsField("savedDay", QVariant.Int))
        fields.append(QgsField("plot_file", QVariant.String))
        fields.append(QgsField("sourceStYr", QVariant.String))
        fields.append(QgsField("dateStYr", QVariant.Int))
        fields.append(QgsField("LULC_StYr", QVariant.String))
        fields.append(QgsField("subCl_StYr", QVariant.String))
        fields.append(QgsField("conf_StYr", QVariant.String))
        fields.append(QgsField("sourceEnYr", QVariant.Int))
        fields.append(QgsField("dateEnYr", QVariant.String))
        fields.append(QgsField("LULC_EnYr", QVariant.String))
        fields.append(QgsField("subCl_EnYr", QVariant.String))
        fields.append(QgsField("deforType", QVariant.String))
        fields.append(QgsField("conf_EnYr", QVariant.String))
        fields.append(QgsField("comments", QVariant.String))

        pr.addAttributes(fields)
        # Coordinate System transformer
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                    desired_coordinate_system, QgsProject.instance())

        input_path = self.parameterAsString(parameters, "input_file", context)
        with open(input_path, newline='') as csvfile:
            fields_to_Remove = ['actively_saved', 'subcategory', 'landuse_subcategory', 'deforestation_nature']
            fields_with_Years = ['image_source', 'land_use', 'confidence']
            fields_Renamed = ['Plot_id', 'SRS', 'X', 'Y', 'operator', 'savedYear', 'savedMonth', 'savedDay',
                              'plot_file', 'sourceStYr', 'dateStYr', 'LULC_StYr', 'subCl_StYr', 'conf_StYr',
                              'sourceEnYr', 'dateEnYr', 'LULC_EnYr', 'subCl_EnYr', 'deforType', 'conf_EnYr', 'comments']
            reader = csv.DictReader(csvfile)
            for line in reader:
                cols = list(line.keys())
                for col in cols:
                    if col in fields_to_Remove: del line[col]
                    elif year := re.findall('(\d{4})', col):
                        split_col_value = col.split(year[0])
                        if (split_col_value[0] in fields_with_Years and not split_col_value[1]): del line[col]
                    else: pass
                geom = QgsGeometry.fromPointXY(QgsPointXY(float(line['location_x']), float(line['location_y'])))
                geom.transform(tr)
                transformed_coords = json.loads(geom.asJson())
                line = dict(zip(fields_Renamed, list(line.values())))
                feature = QgsFeature()
                feature.setGeometry(geom)
                feature.setAttributes(
                    [line['Plot_id'], desired_coordinate_system.authid(), transformed_coords['coordinates'][0],
                     transformed_coords['coordinates'][1], line['operator'], line['savedYear'], line['savedMonth'],
                     line['savedDay'], line['plot_file'], line['sourceStYr'], line['dateStYr'], line['LULC_StYr'],
                     line['subCl_StYr'], line['conf_StYr'], line['sourceEnYr'], line['dateEnYr'], line['LULC_EnYr'],
                     line['subCl_EnYr'], line['deforType'], line['conf_EnYr'], line['comments']])
                pr.addFeatures([feature])
        vl.commitChanges()

        bufferedLayer = processing.run(
            "native:buffer", {
                'INPUT': vl,
                'END_CAP_STYLE': 2, # 2 refers to Square
                'DISTANCE': plot_size/2,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })['OUTPUT']

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context, fields, bufferedLayer.wkbType(), desired_coordinate_system)

        features = bufferedLayer.getFeatures()
        for f in features:
            sink.addFeature(f, QgsFeatureSink.FastInsert)
        return {self.OUTPUT: dest_id}