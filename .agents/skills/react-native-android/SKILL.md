---
name: "react-native-android"
description: "Core principles and constraints for building performant Android apps in React Native."
---

# React Native Android: First Principles

<Callout type="info">
  Your goal is to bridge declarative JavaScript to native Android UI without congestion. Maximize UI thread performance, respect Android hardware constraints, and maintain strict type safety.
</Callout>

## 1. The Big Picture

React Native does not draw pixels directly. It calculates a component tree in JavaScript and passes layout instructions to native Android views.

Performance degrades when the communication layer is congested. Fast apps keep the JS thread lean and run UI updates natively.

## 2. How It Works: Mental Models

### The Two Threads
- **JS Thread:** Handles React lifecycle, state updates, and business logic.
- **UI Thread (Main):** Handles drawing views and receiving touch events.
*Trap:* Executing heavy compute (like large JSON parsing) on the JS thread drops UI frames and causes stuttering.

### Communication
Data must travel between JS and native Android code.
*Intuition:* Avoid passing large datasets back and forth. Keep data and intensive processing as close to the native layer as possible.

## 3. How to Apply It: Directives

<FeatureSection title="Architecture & State">
  - **Structure:** Group by feature (e.g., `/features/auth`), not by technical type (`/components`, `/hooks`). This minimizes cognitive load and keeps context local.
  - **State:** Keep state localized. Use React Context for scoped UI state and Zustand for lightweight global state. Predictable state yields predictable renders.
</FeatureSection>

<FeatureSection title="Android-Specific Mechanics">
  - **Hardware Back Button:** Always implement `BackHandler`. Native Android users intuitively use the physical back button to navigate or close modals. If unhandled, the app will unexpectedly exit.
  - **Keyboard:** Android handles keyboard offsets differently than iOS. Use `KeyboardAvoidingView` with `behavior="height"` for Android.
  - **Safe Area:** Device screens have diverse notches and punch-holes. Use `react-native-safe-area-context` to safely pad headers and bottom bars.
</FeatureSection>

<FeatureSection title="Performance & Memory">
  - **Lists:** Default to `FlashList` (Shopify). If `FlatList` is strictly required, define `getItemLayout` for fixed-size items to eliminate expensive measurement calculations.
  - **Animations:** Use Reanimated 3. All continuous animations must run purely on the UI thread (`runOnUI`) to avoid JS thread blockage.
  - **Images:** Use `react-native-fast-image` for aggressive caching and efficient memory usage on constrained Android devices.
</FeatureSection>

## 4. Verification Checklist

Before finalizing any module, verify:
1. Are all TypeScript props and state strictly typed without using `any`?
2. Are heavy computations memoized with `useMemo`?
3. Is `StyleSheet.create` placed completely outside the component to prevent re-allocation on every render?
4. Are touch targets at least 48x48 dp for Material Design compliance?
