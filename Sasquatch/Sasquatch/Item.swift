//
//  Item.swift
//  Sasquatch
//
//  Created by Randy Zhu on 2026-03-21.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date
    
    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
