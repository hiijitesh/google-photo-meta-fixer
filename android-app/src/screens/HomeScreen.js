import React from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { Text, Card } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

export default function HomeScreen({ navigation }) {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      {/* Header Banner */}
      <View style={styles.header}>
        <MaterialCommunityIcons name="image-multiple-outline" size={40} color="#6366F1" />
        <Text style={styles.headerTitle}>Photos Cleaner</Text>
        <Text style={styles.headerSubtitle}>Reclaim your storage space & fix your timestamps</Text>
      </View>

      {/* Action Cards */}
      <View style={styles.cardContainer}>
        {/* Card 1: Web Exporter */}
        <TouchableOpacity 
          activeOpacity={0.8}
          onPress={() => navigation.navigate('WebView')}
          style={styles.actionCard}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrapper, { backgroundColor: 'rgba(99, 102, 241, 0.15)' }]}>
              <MaterialCommunityIcons name="earth" size={24} color="#6366F1" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>1. Export Metadata</Text>
              <Text style={styles.cardDesc}>Log in to Google Photos and export space-consuming metadata.</Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color="#475569" />
          </View>
        </TouchableOpacity>

        {/* Card 2: Takeout Processor */}
        <TouchableOpacity 
          activeOpacity={0.8}
          onPress={() => navigation.navigate('Process')}
          style={styles.actionCard}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrapper, { backgroundColor: 'rgba(20, 184, 166, 0.15)' }]}>
              <MaterialCommunityIcons name="zip-box-outline" size={24} color="#14B8A6" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>2. Process Takeouts</Text>
              <Text style={styles.cardDesc}>Extract ZIPs and merge EXIF/JSON metadata into your photos.</Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color="#475569" />
          </View>
        </TouchableOpacity>
      </View>

      {/* Guide Section */}
      <View style={styles.guideSection}>
        <Text style={styles.guideTitle}>How it works</Text>
        
        <View style={styles.guideStep}>
          <View style={styles.stepNumber}><Text style={styles.stepNumberText}>✓</Text></View>
          <Text style={styles.guideText}>The Web Exporter runs the Google Photos Toolkit to find quota-consuming files.</Text>
        </View>

        <View style={styles.guideStep}>
          <View style={styles.stepNumber}><Text style={styles.stepNumberText}>✓</Text></View>
          <Text style={styles.guideText}>The Takeout Processor matches photos from Google Takeout ZIPs with the exported CSV to fix your timestamps.</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A', // Slate 900
  },
  contentContainer: {
    padding: 20,
    paddingTop: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#F8FAFC', // Slate 50
    marginTop: 12,
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#94A3B8', // Slate 400
    textAlign: 'center',
    marginTop: 6,
    paddingHorizontal: 20,
  },
  cardContainer: {
    gap: 16,
    marginBottom: 32,
  },
  actionCard: {
    backgroundColor: '#1E293B', // Slate 800
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155', // Slate 700
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconWrapper: {
    width: 48,
    height: 48,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardHeaderText: {
    flex: 1,
    marginLeft: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  cardDesc: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
  },
  guideSection: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  guideTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 16,
  },
  guideStep: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  stepNumber: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#334155',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  stepNumberText: {
    fontSize: 12,
    color: '#6366F1',
    fontWeight: 'bold',
  },
  guideText: {
    flex: 1,
    marginLeft: 12,
    fontSize: 13,
    color: '#94A3B8',
    lineHeight: 18,
  },
});
