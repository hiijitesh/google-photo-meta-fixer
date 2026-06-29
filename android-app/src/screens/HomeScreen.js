import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Button, Text, Card, Title, Paragraph } from 'react-native-paper';

export default function HomeScreen({ navigation }) {
  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Title>Export Metadata</Title>
          <Paragraph>
            Log in to Google Photos and export your metadata to a CSV file.
          </Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button 
            mode="contained" 
            onPress={() => navigation.navigate('WebView')}
          >
            Open Photos Web
          </Button>
        </Card.Actions>
      </Card>

      <Card style={styles.card}>
        <Card.Content>
          <Title>Process Takeout</Title>
          <Paragraph>
            Extract multiple Takeout ZIPs and merge JSON metadata into photos using the generated CSV.
          </Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button 
            mode="contained" 
            onPress={() => navigation.navigate('Process')}
            color="#424242"
          >
            Process ZIPs
          </Button>
        </Card.Actions>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  card: {
    marginBottom: 16,
    elevation: 4,
  },
});
