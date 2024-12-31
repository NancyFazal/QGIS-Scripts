"""
Model exported as python.
Name : CE Interpreted Sample Accuracy
Group : LUC Sampling
With QGIS : 33600
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterNumber,
                       QgsField,
                       QgsFeature,
                       QgsVectorLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterString,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingException,
                       QgsProcessingParameterField,
                       )

from PyQt5.QtCore import QVariant
from qgis import processing
import numpy as np


class CEInterpretedSampleAccuracy(QgsProcessingAlgorithm):
    VECTOR_INPUT = 'VECTOR_INPUT'
    RASTER_INPUT = 'RASTER_INPUT'
    INTERPRETATION_TYPES = ['FOREST_NONFOREST']
    OUTPUT = 'OUTPUT'
    FOREST = 'FOREST'
    NONFOREST = 'NON-FOREST'
    INPUT_PARAM_HELP = {
        "Input Vector": "Interpreted Collect Earth data",
        "Interpreted Data Field": "Name of the column in the Interpreted Collect Earth data layer that contains the interpreted data",
        "Interpretation Type": "Forest / Nonforest",
        "Input Raster": "Raster containing either binary mask (forest/non-forest) or class labels (= integer codes)",
        "Statistic Prefix": "A string value",
        "Forest Class Threshold": "Threshold for the forest class for the Forest/Non-forest interpretation",
        "Output Statistics": "Text file containing the accuracy output"
    }

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CEInterpretedSampleAccuracy()

    def name(self):
        return 'CE Interpreted Sample Accuracy'

    def displayName(self):
        return self.tr('CE Interpreted Sample Accuracy')

    def group(self):
        return self.tr('LUC Sampling')

    def groupId(self):
        return 'luc_sampling'

    def shortHelpString(self):
        return """
                <html><body>
                <p>Evaluating interpreted sample accuracy,Forest / Non-Forest</p> 
                <h2>Parameters</h2>
                """ + "\n".join(f'<h3>{k}</h3><p>{v}</p>' for k, v in self.INPUT_PARAM_HELP.items())

    @classmethod
    # Computes a Confusion Matrix
    def confusion_matrix_binary(cls, actual_classes, predicted_classes):
        fp = 0
        fn = 0
        tp = 0
        tn = 0
        for actual_value, predicted_value in zip(actual_classes, predicted_classes):
            if predicted_value == actual_value:
                if predicted_value == 1:
                    tp += 1
                else:
                    tn += 1
            else:
                if predicted_value == 1:
                    fp += 1
                else:
                    fn += 1
        return np.array([
            [tn, fp],
            [fn, tp]
        ])

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.VECTOR_INPUT,
                self.tr('Interpreted Collect Earth data'),
                types=[QgsProcessing.TypeVectorPolygon],
                defaultValue=None)
        )

        self.addParameter(
            QgsProcessingParameterField(
                'interpreted_data_field',
                self.tr('Interpreted Data Field'),
                parentLayerParameterName=self.VECTOR_INPUT)
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                'INTERPRETATION_TYPE',
                self.tr('Interpretation Type'),
                options=self.INTERPRETATION_TYPES,
                defaultValue="FOREST_NONFOREST",
                allowMultiple=False)
        )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                'INPUT_RASTER',
                self.tr('Input Raster'),
                defaultValue=None)
        )

        self.addParameter(
            QgsProcessingParameterString(
                'STATISTIC_PREFIX',
                self.tr('Statistic Prefix'),
                defaultValue=None)
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                'FOREST_CLASS_THRESHOLD',
                self.tr('Forest Class Threshold'),
                defaultValue=0.7,
                type=QgsProcessingParameterNumber.Double)
        )

        self.addParameter(
            QgsProcessingParameterFile(
                'OUTPUT_STATISTICS',
                self.tr('Output Statistics'),
                extension="txt"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        input_vector = self.parameterAsVectorLayer(parameters, self.VECTOR_INPUT, context)
        input_raster = self.parameterAsRasterLayer(parameters, 'INPUT_RASTER', context)
        interpreted_data_field = self.parameterAsString(parameters, 'INTERPRETED_DATA_FIELD', context)
        interpretation_type = self.parameterAsEnums(parameters, 'INTERPRETATION_TYPE', context)
        statistic_prefix = self.parameterAsString(parameters, 'STATISTIC_PREFIX', context)
        forest_class_threshold = self.parameterAsDouble(parameters, 'FOREST_CLASS_THRESHOLD', context)
        output_statistics = self.parameterAsFileOutput(parameters, 'OUTPUT_STATISTICS', context)

        # Find Classes Forest(1)/ Non-Forest(0)
        def getPredictedClass(meanStat, forestThreshold):
            if (meanStat < forestThreshold):
                return 1
            else:
                return 0

        def getActualClass(value):
            if (value.lower() == self.FOREST.lower()):
                return 1
            elif (value.lower() == self.NONFOREST.lower()):
                return 0
            else:
                raise QgsProcessingException(
                    "Invalid Interpreted data field value - Allowed values are forest or Non-forest")

        # get Statistics to Calculate
        def getStatisticstoCalculate(interpretationType):
            for type in self.INTERPRETATION_TYPES:
                print(type)
                if (type == 'FOREST_NONFOREST'):
                    return '2'  # 2 refers to MEAN
                else:
                    return None

        #Run Zonal Statistics Algorithm
        zonalStatistics_result = processing.run(
            'native:zonalstatisticsfb',
            {
                'INPUT': input_vector,
                'INPUT_RASTER': input_raster,
                'STATISTICS': getStatisticstoCalculate(interpretation_type),
                'RASTER_BAND': 1,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })['OUTPUT']


        #Add new Qgs field to the input Vector Layer and update the attribute values
        #Collective Actual and Predicted Classes values

        actual_Classes = []
        predicted_Classes = []
        input_vector.startEditing()
        new_field = statistic_prefix + '_MEAN'
        input_vector.addAttribute(QgsField(new_field, QVariant.Double))
        statistic = zonalStatistics_result.fields().indexFromName("_mean")
        interpreted_field = zonalStatistics_result.fields().indexFromName(interpreted_data_field)
        field_idx = input_vector.fields().indexOf(new_field)
        input_vector_features = input_vector.getFeatures()

        #The loop relies on the features in "zonalStatistics_result" and "input_vector_features" to be of the same order

        for feature in zonalStatistics_result.getFeatures():
            stat_Val = feature.attributes()[statistic]
            actual_Class_Val = feature.attributes()[interpreted_field]
            predicted_Classes.append(getPredictedClass(stat_Val, forest_class_threshold))
            actual_Classes.append(getActualClass(actual_Class_Val))
            f = next(input_vector_features)
            input_vector.changeAttributeValue(f.id(), field_idx, stat_Val)
        input_vector.commitChanges()

        print(actual_Classes)
        print(predicted_Classes)

        confusion_matrix = CEInterpretedSampleAccuracy.confusion_matrix_binary(actual_Classes, predicted_Classes)

        # Write to text file
        f = open(output_statistics, 'wt')
        f.write(str(confusion_matrix))
        f.close()

        return {'OUTPUT': output_statistics}