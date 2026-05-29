import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

Future initFirebase() async {
  if (kIsWeb) {
    await Firebase.initializeApp(
        options: FirebaseOptions(
            apiKey: "AIzaSyA6SRPjW-rZH02aoLVC5PJrHVWBBKBxK4Q",
            authDomain: "pppdui-vmjj8r.firebaseapp.com",
            projectId: "pppdui-vmjj8r",
            storageBucket: "pppdui-vmjj8r.firebasestorage.app",
            messagingSenderId: "225996092671",
            appId: "1:225996092671:web:936023c59993db259ac8ca",
            measurementId: "G-QBH8NRRKL0"));
  } else {
    await Firebase.initializeApp();
  }
}
