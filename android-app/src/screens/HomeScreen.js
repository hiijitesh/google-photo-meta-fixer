import React from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity, Dimensions } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

export default function HomeScreen({ navigation }) {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      {/* Brand Identity / Header */}
      <View style={styles.header}>
        <View style={styles.logoBadge}>
          <MaterialCommunityIcons name="lightning-bolt" size={28} color="#00F2FE" />
        </View>
        <Text style={styles.headerTitle}>LUMINA PHOTOS</Text>
        <Text style={styles.headerSubtitle}>
          Commercial-grade optimization & EXIF timestamp correction for Google Photos Takeouts.
        </Text>
      </View>

      {/* Mock Live Stats Dashboard */}
      <View style={styles.statsContainer}>
        <View style={styles.statBox}>
          <Text style={styles.statNumber}>1.2 TB</Text>
          <Text style={styles.statLabel}>Optimized</Text>
        </View>
        <View style={[styles.statBox, { borderColor: '#6366F1' }]}>
          <Text style={[styles.statNumber, { color: '#6366F1' }]}>42.6K</Text>
          <Text style={styles.statLabel}>EXIF Restored</Text>
        </View>
        <View style={[styles.statBox, { borderColor: '#14B8A6' }]}>
          <Text style={[styles.statNumber, { color: '#14B8A6' }]}>18.4K</Text>
          <Text style={styles.statLabel}>Cleaned Files</Text>
        </View>
      </View>

      {/* Main Actions */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>OPTIMIZATION TOOLS</Text>
      </View>

      <View style={styles.cardContainer}>
        {/* Action 1: Web Exporter */}
        <TouchableOpacity 
          activeOpacity={0.85}
          onPress={() => navigation.navigate('CloudAudit')}
          style={[styles.actionCard, { borderColor: '#6366F1' }]}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrapper, { backgroundColor: 'rgba(99, 102, 241, 0.12)' }]}>
              <MaterialCommunityIcons name="earth" size={26} color="#6366F1" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>1. Cloud Audit Center</Text>
              <Text style={styles.cardDesc}>
                Audit cloud quotas natively via Google Photos API, or import CSV index reports from Kiwi Browser.
              </Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color="#6366F1" />
          </View>
        </TouchableOpacity>

        {/* Action 2: Takeout Processor */}
        <TouchableOpacity 
          activeOpacity={0.85}
          onPress={() => navigation.navigate('Process')}
          style={[styles.actionCard, { borderColor: '#14B8A6' }]}
        >
          <View style={styles.cardHeader}>
            <View style={[styles.iconWrapper, { backgroundColor: 'rgba(20, 184, 166, 0.12)' }]}>
              <MaterialCommunityIcons name="zip-box" size={26} color="#14B8A6" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>2. Native Takeout Parser</Text>
              <Text style={styles.cardDesc}>
                Extract multi-gigabyte Takeout ZIPs directly to local storage and inject JSON EXIF metadata.
              </Text>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={24} color="#14B8A6" />
          </View>
        </TouchableOpacity>
      </View>

      {/* Stepped Process Guide */}
      <View style={styles.guideContainer}>
        <Text style={styles.guideTitle}>ENTERPRISE WORKFLOW</Text>
        
        <View style={styles.timelineItem}>
          <View style={styles.timelineIconContainer}>
            <View style={[styles.timelineIcon, { backgroundColor: '#6366F1' }]}>
              <MaterialCommunityIcons name="export" size={14} color="#FFF" />
            </View>
            <View style={styles.timelineLine} />
          </View>
          <View style={styles.timelineContent}>
            <Text style={styles.timelineStepTitle}>EXPORT METADATA</Text>
            <Text style={styles.timelineStepDesc}>
              Use the userscript inside the web panel to capture real size quotas and locate duplicates.
            </Text>
          </View>
        </View>

        <View style={styles.timelineItem}>
          <View style={styles.timelineIconContainer}>
            <View style={[styles.timelineIcon, { backgroundColor: '#14B8A6' }]}>
              <MaterialCommunityIcons name="hammer-wrench" size={14} color="#FFF" />
            </View>
            <View style={styles.timelineLine} />
          </View>
          <View style={styles.timelineContent}>
            <Text style={styles.timelineStepTitle}>REPAIR EXIF TAGS</Text>
            <Text style={styles.timelineStepDesc}>
              Parse local ZIP files. Write date, GPS location, and other metadata directly back into photo EXIF headers.
            </Text>
          </View>
        </View>

        <View style={styles.timelineItem}>
          <View style={[styles.timelineIconContainer, { paddingBottom: 0 }]}>
            <View style={[styles.timelineIcon, { backgroundColor: '#00F2FE' }]}>
              <MaterialCommunityIcons name="cloud-sync" size={14} color="#000" />
            </View>
          </View>
          <View style={styles.timelineContent}>
            <Text style={styles.timelineStepTitle}>CLOUD SYNCHRONIZATION</Text>
            <Text style={styles.timelineStepDesc}>
              Upload clean local files directly back to Drive using optimized multi-threaded syncing.
            </Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A0F1D', // Premium deep dark theme
  },
  contentContainer: {
    padding: 20,
    paddingTop: 30,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 28,
  },
  logoBadge: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1.5,
    borderColor: '#334155',
    shadowColor: '#00F2FE',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 5,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '900',
    color: '#FFFFFF',
    letterSpacing: 2,
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 18,
    paddingHorizontal: 15,
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 32,
    gap: 10,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#131929',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  statNumber: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#00F2FE',
    letterSpacing: 0.5,
  },
  statLabel: {
    fontSize: 10,
    color: '#64748B',
    marginTop: 4,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  sectionHeader: {
    marginBottom: 12,
    paddingHorizontal: 4,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#475569',
    letterSpacing: 1.5,
  },
  cardContainer: {
    gap: 16,
    marginBottom: 32,
  },
  actionCard: {
    backgroundColor: '#131929',
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconWrapper: {
    width: 52,
    height: 52,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  cardHeaderText: {
    flex: 1,
    marginLeft: 16,
    marginRight: 8,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  cardDesc: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 6,
    lineHeight: 16,
  },
  guideContainer: {
    backgroundColor: '#131929',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  guideTitle: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#475569',
    letterSpacing: 1.5,
    marginBottom: 20,
  },
  timelineItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  timelineIconContainer: {
    alignItems: 'center',
    marginRight: 16,
  },
  timelineIcon: {
    width: 26,
    height: 26,
    borderRadius: 13,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  timelineLine: {
    width: 2,
    height: 55,
    backgroundColor: '#1E293B',
  },
  timelineContent: {
    flex: 1,
    paddingBottom: 24,
  },
  timelineStepTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  timelineStepDesc: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 4,
    lineHeight: 16,
  },
});
